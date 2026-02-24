import json
import time
import gzip
import urllib.request
import urllib.error
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup


CIKS = {
    "berkshire": "0001067983",
    "bridgewater": "0001350694",
    "himalaya": "0001603466",
    "hh": "0001848853",
}

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{}.json"

USER_AGENT = "13f-dashboard (greatzoom69@gmail.com)"
MIN_DELAY_SEC = 1.0
TIMEOUT_SEC = 30


def _sleep_polite():
    time.sleep(MIN_DELAY_SEC)


def fetch_bytes(url: str) -> Tuple[bytes, Dict[str, str]]:
    headers = {
    "User-Agent": "13f-dashboard/1.0 (Contact: greatzoom69@gmail.com)",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Accept-Encoding": "identity",
    }

    last_err: Optional[Exception] = None
    for attempt in range(1, 6):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
                raw = resp.read()
                h = {k.lower(): v for k, v in resp.headers.items()}

            enc = h.get("content-encoding", "").lower()
            if "gzip" in enc or (len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B):
                raw = gzip.decompress(raw)

            _sleep_polite()
            return raw, h
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(2**attempt, 10))
                continue
            raise
        except Exception as e:
            last_err = e
            time.sleep(min(2**attempt, 10))
            continue

    raise RuntimeError(f"Failed to fetch after retries: {url}. Last error: {last_err}")


def fetch_json(url: str) -> Any:
    raw, _ = fetch_bytes(url)
    return json.loads(raw.decode("utf-8"))


def quarter_from_date(yyyy_mm_dd: str) -> str:
    y, m, _ = yyyy_mm_dd.split("-")
    m = int(m)
    q = 1 if m <= 3 else 2 if m <= 6 else 3 if m <= 9 else 4
    return f"{y}Q{q}"


def pick_latest_13f_with_reportdate(recent: Dict[str, List[Any]]) -> Optional[Dict[str, Any]]:
    forms = recent.get("form", [])
    accs = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    primary_docs = recent.get("primaryDocument", [])

    for i in range(len(forms)):
        form = forms[i]
        if form not in ("13F-HR", "13F-HR/A"):
            continue
        if i >= len(report_dates) or not report_dates[i]:
            continue
        acc = accs[i] if i < len(accs) else None
        if not acc:
            continue

        # must have a primary document (usually .htm)
        primary = primary_docs[i] if i < len(primary_docs) else None
        if not primary:
            continue

        return {
            "form": form,
            "accessionNumber": acc,
            "filingDate": filing_dates[i] if i < len(filing_dates) else None,
            "reportDate": report_dates[i],
            "primaryDocument": primary,
        }

    return None


def build_primary_doc_url(cik: str, accession_with_dash: str, primary_doc: str) -> str:
    cik_nolead = str(int(cik))
    acc_nodash = accession_with_dash.replace("-", "")
    # Use sec.gov (not data.sec.gov) for document files; more consistently available
    return f"https://www.sec.gov/Archives/edgar/data/{cik_nolead}/{acc_nodash}/{primary_doc}"


def find_infotable_from_index(cik: str, acc_with_dash: str) -> Tuple[str, str]:
    """
    Look up filing index page and find the best candidate infotable XML filename.
    Returns (url, filename). Uses sec.gov Archives (more consistent).
    """
    cik_nolead = str(int(cik))
    acc_nodash = acc_with_dash.replace("-", "")

    base_dir = f"https://www.sec.gov/Archives/edgar/data/{cik_nolead}/{acc_nodash}/"
    index_url = f"{base_dir}{acc_with_dash}-index.html"

    html_bytes, _ = fetch_bytes(index_url)
    html = html_bytes.decode("utf-8", errors="ignore")

    soup = BeautifulSoup(html, "lxml")

    hrefs = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        # href could be absolute or relative
        fname = href.split("/")[-1]
        hrefs.append(fname)

    # Prefer these filenames (most common for 13F holdings)
    def score(name: str) -> int:
        n = name.lower()
        if not n.endswith(".xml"):
            return 999
        if "primary_doc" in n:
            return 999
        if "form13f" in n and "infotable" in n:
            return 0
        if "form13f" in n:
            return 1
        if "infotable" in n:
            return 2
        if "informationtable" in n:
            return 3
        if "info" in n and "table" in n:
            return 4
        return 50

    candidates = sorted(set(hrefs), key=score)
    candidates = [c for c in candidates if score(c) < 999]

    if not candidates:
        raise RuntimeError(f"No infotable-like XML found on index page: {index_url}")

    fname = candidates[0]
    return base_dir + fname, fname

def parse_infotable_xml(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parse 13F information table XML (infoTable nodes).
    """
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)

    def strip_ns(tag: str) -> str:
        return tag.split("}", 1)[-1] if "}" in tag else tag

    holdings: List[Dict[str, Any]] = []

    for node in root.iter():
        if strip_ns(node.tag) != "infoTable":
            continue

        def find_text(tag_name: str) -> str:
            for child in node.iter():
                if strip_ns(child.tag) == tag_name:
                    return (child.text or "").strip()
            return ""

        issuer = find_text("nameOfIssuer")
        cusip = find_text("cusip")
        value_k = find_text("value")
        shares = find_text("sshPrnamt")

        if not issuer:
            continue

        try:
            value_usd_k = int(value_k) if value_k else 0
        except ValueError:
            value_usd_k = 0

        try:
            shares_i = int(float(shares)) if shares else 0
        except ValueError:
            shares_i = 0

        holdings.append(
            {
                "issuer": issuer,
                "cusip": cusip or None,
                "value_usd_k": value_usd_k,
                "shares": shares_i,
            }
        )

    return holdings

def parse_13f_holdings_from_html(html: str) -> List[Dict[str, Any]]:
    """
    Parse holdings from 13F HTML information table.
    This is heuristic: it searches for tables containing headers like
    'Name of Issuer', 'CUSIP', 'Value', 'SHRS or PRN AMT', etc.
    """
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")

    best_rows = []
    best_score = 0
    best_headers = None

    def norm(s: str) -> str:
        return " ".join((s or "").strip().lower().split())

    wanted = [
        "name of issuer",
        "cusip",
        "value",
        "shrs or prn amt",
        "ssh prnamt",
        "shares",
    ]

    for t in tables:
        # grab first row as header candidate
        trs = t.find_all("tr")
        if not trs:
            continue

        header_cells = trs[0].find_all(["th", "td"])
        headers = [norm(c.get_text(" ", strip=True)) for c in header_cells]
        if not headers:
            continue

        score = sum(1 for w in wanted if any(w in h for h in headers))
        if score > best_score:
            best_score = score
            best_rows = trs
            best_headers = headers

    if best_score < 2 or not best_rows or not best_headers:
        # couldn't find a good table
        return []

    # Map columns
    headers = best_headers

    def find_col(pred) -> Optional[int]:
        for idx, h in enumerate(headers):
            if pred(h):
                return idx
        return None

    col_issuer = find_col(lambda h: "name of issuer" in h or h == "issuer" or "issuer" in h)
    col_cusip = find_col(lambda h: "cusip" in h)
    col_value = find_col(lambda h: h == "value" or "value" in h)
    col_shares = find_col(lambda h: "shrs" in h or "ssh prnamt" in h or "prn amt" in h or "shares" in h)

    holdings: List[Dict[str, Any]] = []

    # data rows start after header row
    for tr in best_rows[1:]:
        tds = tr.find_all(["td", "th"])
        if not tds:
            continue

        cells = [c.get_text(" ", strip=True) for c in tds]

        def get(i: Optional[int]) -> str:
            if i is None:
                return ""
            return cells[i] if i < len(cells) else ""

        issuer = get(col_issuer).strip()
        if not issuer or issuer.lower().startswith("name of issuer"):
            continue

        cusip = get(col_cusip).strip() or None

        # value is usually in $ thousands on 13F tables
        value_raw = get(col_value).replace(",", "").strip()
        try:
            value_usd_k = int(float(value_raw)) if value_raw else 0
        except ValueError:
            value_usd_k = 0

        shares_raw = get(col_shares).replace(",", "").strip()
        try:
            shares = int(float(shares_raw)) if shares_raw else 0
        except ValueError:
            shares = 0

        holdings.append(
            {
                "issuer": issuer,
                "cusip": cusip,
                "value_usd_k": value_usd_k,
                "shares": shares,
            }
        )

    return holdings



def main():
    print("START main()")
    import os
    import shutil

    TMP_DIR = "data_tmp"
    OUT_DIR = "data/13f"

    # 清理并创建临时目录
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    os.makedirs(os.path.join(TMP_DIR, "13f"), exist_ok=True)

    staged_slugs = []

    for slug, cik in CIKS.items():
        sub = fetch_json(SUBMISSIONS.format(cik.zfill(10)))
        recent = sub.get("filings", {}).get("recent", {})

        latest = pick_latest_13f_with_reportdate(recent)
        if not latest:
            print(f"[{slug}] No 13F-HR found with reportDate + primaryDocument.")
            continue

        acc = latest["accessionNumber"]
        filing_date = latest.get("filingDate") or ""
        report_date = latest.get("reportDate") or ""
        quarter = quarter_from_date(report_date) if report_date else ""

        infotable_url, infotable_fname = find_infotable_from_index(cik, acc)
        print(f"[{slug}] Fetching infotable: {infotable_url}")

        xml_bytes, _ = fetch_bytes(infotable_url)
        holdings = parse_infotable_xml(xml_bytes)

        total_value = sum(h["value_usd_k"] for h in holdings) or 1
        for h in holdings:
            h["weight"] = round(h["value_usd_k"] / total_value, 6)

        holdings_sorted = sorted(holdings, key=lambda x: x["value_usd_k"], reverse=True)
        top1 = holdings_sorted[0]["issuer"] if holdings_sorted else None

        out = {
            "name": sub.get("name") or slug,
            "latest": {
                "quarter": quarter,
                "filing_date": filing_date,
                "infotable_url": infotable_url,
            },
            "stats": {
                "holdings": len(holdings_sorted),
                "top1": top1,
                "changes": {"new": 0, "add": 0, "trim": 0, "exit": 0},
            },
            "holdings": [
                {
                    "issuer": h["issuer"],
                    "value_usd_k": h["value_usd_k"],
                    "weight": h["weight"],
                    "shares": h["shares"],
                    "cusip": h.get("cusip"),
                }
                for h in holdings_sorted
            ],
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

        # ---- 验证 ----
        if not out.get("latest", {}).get("quarter"):
            raise RuntimeError(f"[{slug}] validation failed: missing latest.quarter")

        if not isinstance(out.get("holdings"), list):
            raise RuntimeError(f"[{slug}] validation failed: holdings is not a list")

        for i, h in enumerate(out["holdings"][:50]):
            if not h.get("issuer"):
                raise RuntimeError(f"[{slug}] validation failed: holdings[{i}] missing issuer")

            v = h.get("value_usd_k")
            if not isinstance(v, (int, float)) or v < 0:
                raise RuntimeError(f"[{slug}] validation failed: holdings[{i}] invalid value_usd_k={v}")

        # ---- 写入临时目录 ----
        tmp_path = os.path.join(TMP_DIR, "13f", f"{slug}.json")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        staged_slugs.append(slug)
        print(f"[{slug}] Staged successfully")

    # ---- 所有成功后再覆盖 data ----
    os.makedirs(OUT_DIR, exist_ok=True)

    for slug in staged_slugs:
        src = os.path.join(TMP_DIR, "13f", f"{slug}.json")
        dst = os.path.join(OUT_DIR, f"{slug}.json")
        tmp_dst = dst + ".tmp"

        shutil.copyfile(src, tmp_dst)
        os.replace(tmp_dst, dst)

    shutil.rmtree(TMP_DIR, ignore_errors=True)
    print(f"Promoted {len(staged_slugs)} files to data/13f")
if __name__ == "__main__":
    main()