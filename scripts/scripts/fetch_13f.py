import json
import os
import time
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"
OUT_DIR = ROOT / "public" / "data" / "13f"

SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data/{cik_nolead}/{accession_nodash}/"
SEC_INDEX_JSON = SEC_ARCHIVES_BASE + "index.json"

# ====== IMPORTANT ======
# SEC asks automated clients to identify themselves via User-Agent with contact info.
# Put it in GitHub Actions secret: SEC_USER_AGENT
# Example: "YourName your_email@example.com"
# =======================

def sec_get_json(url: str, user_agent: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def sec_get_text(url: str, user_agent: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")

def clean_cik(cik: str) -> str:
    cik = cik.strip()
    if not cik.isdigit():
        raise ValueError(f"CIK must be digits: {cik}")
    return cik.zfill(10)

def cik_nolead(cik10: str) -> str:
    return str(int(cik10))  # remove leading zeros

def accession_nodash(accession: str) -> str:
    return accession.replace("-", "")

def pick_latest_13f(sub: dict) -> Optional[Tuple[str, str, str]]:
    """
    returns (accessionNumber, filingDate, form)
    preference: latest 13F-HR/A if newer? For simplicity pick newest among 13F-HR and 13F-HR/A
    """
    recent = sub.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accession = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    if not forms:
        return None

    candidates = []
    for f, a, d in zip(forms, accession, filing_dates):
        if f in ("13F-HR", "13F-HR/A"):
            candidates.append((d, a, f))
    if not candidates:
        return None
    # newest filingDate
    candidates.sort(key=lambda x: x[0], reverse=True)
    d, a, f = candidates[0]
    return (a, d, f)

def find_infotable_url(cik10: str, accession: str, user_agent: str) -> Optional[str]:
    idx = sec_get_json(
        SEC_INDEX_JSON.format(cik_nolead=cik_nolead(cik10), accession_nodash=accession_nodash(accession)),
        user_agent
    )
    items = idx.get("directory", {}).get("item", [])
    # Common filenames include: infotable.xml, form13fInfoTable.xml, primary_doc.xml in some cases
    preferred = []
    for it in items:
        name = (it.get("name") or "").lower()
        if name.endswith(".xml") and ("infotable" in name or "informationtable" in name or "form13f" in name):
            preferred.append(it.get("name"))
    if not preferred:
        # fallback: any xml with "info" and "table"
        for it in items:
            name = (it.get("name") or "").lower()
            if name.endswith(".xml") and ("info" in name and "table" in name):
                preferred.append(it.get("name"))
    if not preferred:
        return None

    filename = preferred[0]
    return SEC_ARCHIVES_BASE.format(cik_nolead=cik_nolead(cik10), accession_nodash=accession_nodash(accession)) + filename

def parse_infotable_xml(xml_text: str) -> List[dict]:
    """
    Parse 13F information table XML.
    Output normalized rows:
      {cusip, issuer, class, value_usd_k, shares, put_call, discretion, voting_sole, voting_shared, voting_none}
    Note: value is usually reported in thousands of dollars in 13F.
    """
    # Some filings include namespaces; handle generically
    root = ET.fromstring(xml_text)
    # Find all "infoTable" elements regardless of namespace
    def strip_ns(tag: str) -> str:
        return tag.split("}")[-1] if "}" in tag else tag

    rows = []
    for elem in root.iter():
        if strip_ns(elem.tag) == "infoTable":
            row = {}
            # children names vary; read by tag
            for ch in list(elem):
                key = strip_ns(ch.tag)
                text = (ch.text or "").strip()
                row[key] = text
            # Normalize
            issuer = row.get("nameOfIssuer") or row.get("issuerName") or ""
            title = row.get("titleOfClass") or ""
            cusip = row.get("cusip") or ""
            value = row.get("value") or ""  # usually in $ thousands
            ssh_prn_amt = row.get("sshPrnamt") or row.get("sshPrnAmt") or ""
            ssh_prn_type = row.get("sshPrnamtType") or row.get("sshPrnAmtType") or ""
            put_call = row.get("putCall") or ""
            discretion = row.get("investmentDiscretion") or ""
            voting = row.get("votingAuthority") or ""  # sometimes nested; try read subfields below

            # Voting subfields can be nested elements, so scan for them
            voting_sole = voting_shared = voting_none = ""
            for v in elem.iter():
                if strip_ns(v.tag) in ("Sole", "Shared", "None"):
                    if strip_ns(v.tag) == "Sole":
                        voting_sole = (v.text or "").strip()
                    elif strip_ns(v.tag) == "Shared":
                        voting_shared = (v.text or "").strip()
                    elif strip_ns(v.tag) == "None":
                        voting_none = (v.text or "").strip()

            def to_int(x: str) -> int:
                x = re.sub(r"[^\d]", "", x or "")
                return int(x) if x else 0

            def to_value_k(x: str) -> int:
                x = re.sub(r"[^\d]", "", x or "")
                return int(x) if x else 0

            rows.append({
                "issuer": issuer,
                "class": title,
                "cusip": cusip,
                "value_usd_k": to_value_k(value),
                "shares": to_int(ssh_prn_amt),
                "shares_type": ssh_prn_type,
                "put_call": put_call,
                "discretion": discretion,
                "voting_sole": to_int(voting_sole),
                "voting_shared": to_int(voting_shared),
                "voting_none": to_int(voting_none)
            })
    return rows

def compute_weights(rows: List[dict]) -> List[dict]:
    total = sum(r.get("value_usd_k", 0) for r in rows) or 1
    out = []
    for r in rows:
        rr = dict(r)
        rr["weight"] = rr.get("value_usd_k", 0) / total
        out.append(rr)
    out.sort(key=lambda x: x.get("value_usd_k", 0), reverse=True)
    return out

def diff_holdings(cur: List[dict], prev: List[dict]) -> List[dict]:
    """
    Diff by CUSIP (most stable). Mark change types: NEW / ADD / TRIM / EXIT / SAME.
    shares delta and value delta in % relative to prev.
    """
    prev_map = {r["cusip"]: r for r in prev if r.get("cusip")}
    cur_map = {r["cusip"]: r for r in cur if r.get("cusip")}

    diffs = []
    all_cusips = set(prev_map.keys()) | set(cur_map.keys())

    for cusip in all_cusips:
        a = cur_map.get(cusip)
        b = prev_map.get(cusip)
        if a and not b:
            diffs.append({
                "cusip": cusip,
                "issuer": a.get("issuer", ""),
                "change": "NEW",
                "shares_delta": a.get("shares", 0),
                "shares_delta_pct": None,
                "value_delta_k": a.get("value_usd_k", 0),
                "value_delta_pct": None,
                "cur_weight": a.get("weight", 0.0),
                "prev_weight": 0.0
            })
        elif (not a) and b:
            diffs.append({
                "cusip": cusip,
                "issuer": b.get("issuer", ""),
                "change": "EXIT",
                "shares_delta": -b.get("shares", 0),
                "shares_delta_pct": -1.0,
                "value_delta_k": -b.get("value_usd_k", 0),
                "value_delta_pct": -1.0,
                "cur_weight": 0.0,
                "prev_weight": b.get("weight", 0.0)
            })
        else:
            # both exist
            cur_sh = a.get("shares", 0)
            prev_sh = b.get("shares", 0)
            cur_val = a.get("value_usd_k", 0)
            prev_val = b.get("value_usd_k", 0)

            if prev_sh == 0:
                sh_pct = None
            else:
                sh_pct = (cur_sh - prev_sh) / prev_sh

            if prev_val == 0:
                val_pct = None
            else:
                val_pct = (cur_val - prev_val) / prev_val

            if prev_sh == 0 and cur_sh > 0:
                change = "NEW"
            elif cur_sh == prev_sh:
                change = "SAME"
            elif cur_sh > prev_sh:
                change = "ADD"
            else:
                change = "TRIM"

            diffs.append({
                "cusip": cusip,
                "issuer": a.get("issuer", ""),
                "change": change,
                "shares_delta": cur_sh - prev_sh,
                "shares_delta_pct": sh_pct,
                "value_delta_k": cur_val - prev_val,
                "value_delta_pct": val_pct,
                "cur_weight": a.get("weight", 0.0),
                "prev_weight": b.get("weight", 0.0)
            })

    # Sort by absolute value delta, then NEW/EXIT first-ish
    def rank(d):
        priority = {"NEW": 0, "EXIT": 1, "ADD": 2, "TRIM": 3, "SAME": 4}
        return (priority.get(d["change"], 9), -abs(d.get("value_delta_k", 0)))

    diffs.sort(key=rank)
    return diffs

def quarter_from_date(d: str) -> str:
    # d: YYYY-MM-DD
    dt = datetime.strptime(d, "%Y-%m-%d")
    q = (dt.month - 1) // 3 + 1
    return f"{dt.year} Q{q}"

def ensure_dirs():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not user_agent:
        raise RuntimeError("Missing SEC_USER_AGENT env var. Set it as a GitHub Actions secret.")

    ensure_dirs()
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    managers = cfg.get("managers", [])
    now_iso = datetime.now(timezone.utc).isoformat()

    managers_out = []
    for m in managers:
        slug = m["slug"]
        name = m["name"]
        cik10 = clean_cik(m["cik"])

        # Be polite to SEC
        time.sleep(0.25)

        sub = sec_get_json(SEC_SUBMISSIONS.format(cik=cik10), user_agent)
        latest = pick_latest_13f(sub)
        if not latest:
            managers_out.append({
                "slug": slug,
                "name": name,
                "cik": cik10,
                "status": "no_13f_found"
            })
            continue

        accession, filing_date, form = latest

        # Try to find previous 13F too (for diff)
        recent = sub.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accession_list = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        thirteen = [(d, a, f) for f, a, d in zip(forms, accession_list, filing_dates) if f in ("13F-HR", "13F-HR/A")]
        thirteen.sort(key=lambda x: x[0], reverse=True)
        prev_accession = prev_filing_date = prev_form = None
        if len(thirteen) >= 2:
            prev_filing_date, prev_accession, prev_form = thirteen[1]

        # Fetch latest infotable
        time.sleep(0.25)
        infotable_url = find_infotable_url(cik10, accession, user_agent)
        if not infotable_url:
            managers_out.append({
                "slug": slug,
                "name": name,
                "cik": cik10,
                "status": "infotable_not_found",
                "latest": {"accession": accession, "filing_date": filing_date, "form": form}
            })
            continue

        xml_text = sec_get_text(infotable_url, user_agent)
        cur_rows = compute_weights(parse_infotable_xml(xml_text))

        prev_rows = []
        if prev_accession:
            time.sleep(0.25)
            prev_url = find_infotable_url(cik10, prev_accession, user_agent)
            if prev_url:
                prev_xml = sec_get_text(prev_url, user_agent)
                prev_rows = compute_weights(parse_infotable_xml(prev_xml))

        diffs = diff_holdings(cur_rows, prev_rows) if prev_rows else []

        # Summary counts
        new_cnt = sum(1 for d in diffs if d["change"] == "NEW")
        exit_cnt = sum(1 for d in diffs if d["change"] == "EXIT")
        add_cnt = sum(1 for d in diffs if d["change"] == "ADD")
        trim_cnt = sum(1 for d in diffs if d["change"] == "TRIM")

        top1 = cur_rows[0]["issuer"] if cur_rows else ""
        latest_q = quarter_from_date(filing_date)

        manager_payload = {
            "slug": slug,
            "name": name,
            "cik": cik10,
            "updated_at_utc": now_iso,
            "latest": {
                "quarter": latest_q,
                "filing_date": filing_date,
                "form": form,
                "accession": accession,
                "infotable_url": infotable_url
            },
            "previous": ({
                "quarter": quarter_from_date(prev_filing_date),
                "filing_date": prev_filing_date,
                "form": prev_form,
                "accession": prev_accession
            } if prev_accession else None),
            "stats": {
                "holdings": len(cur_rows),
                "top1": top1,
                "changes": {
                    "new": new_cnt,
                    "exit": exit_cnt,
                    "add": add_cnt,
                    "trim": trim_cnt
                }
            },
            "holdings": cur_rows[:400],  # safety cap
            "diffs": diffs[:800]
        }

        (OUT_DIR / f"{slug}.json").write_text(json.dumps(manager_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        managers_out.append({
            "slug": slug,
            "name": name,
            "cik": cik10,
            "status": "ok",
            "latest_quarter": latest_q,
            "filing_date": filing_date,
            "holdings": len(cur_rows),
            "top1": top1,
            "changes": {"new": new_cnt, "exit": exit_cnt, "add": add_cnt, "trim": trim_cnt}
        })

    index_payload = {
        "updated_at_utc": now_iso,
        "managers": managers_out
    }
    (OUT_DIR / "index.json").write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote:", OUT_DIR / "index.json")

if __name__ == "__main__":
    main()
