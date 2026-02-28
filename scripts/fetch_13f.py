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
    pair = pick_latest_and_previous_13f(recent)
    return pair[0] if pair else None


def _quarter_from_filing(filing: Dict[str, Any]) -> str:
    """Quarter from reportDate if present, else from filingDate."""
    report_date = filing.get("reportDate") or ""
    if report_date:
        return quarter_from_date(report_date)
    filing_date = filing.get("filingDate") or ""
    if filing_date:
        return quarter_from_date(filing_date)
    return ""


def pick_latest_and_previous_13f(recent: Dict[str, List[Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    From filings list (by filingDate desc), return (latest, previous).
    Both 13F-HR or 13F-HR/A with primaryDocument; previous = second in list.
    """
    forms = recent.get("form", [])
    accs = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    primary_docs = recent.get("primaryDocument", [])

    candidates: List[Dict[str, Any]] = []
    for i in range(len(forms)):
        form = forms[i]
        if form not in ("13F-HR", "13F-HR/A"):
            continue
        acc = accs[i] if i < len(accs) else None
        if not acc:
            continue
        primary = primary_docs[i] if i < len(primary_docs) else None
        if not primary:
            continue
        filing_date = filing_dates[i] if i < len(filing_dates) else ""
        report_date = report_dates[i] if i < len(report_dates) else ""
        candidates.append({
            "form": form,
            "accessionNumber": acc,
            "filingDate": filing_date,
            "reportDate": report_date,
            "primaryDocument": primary,
        })

    if not candidates:
        return (None, None)
    # Sort by filingDate descending (most recent first)
    candidates.sort(key=lambda x: (x.get("filingDate") or ""), reverse=True)
    latest = candidates[0]
    previous: Optional[Dict[str, Any]] = candidates[1] if len(candidates) >= 2 else None
    return (latest, previous)


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


def is_previous_quarter(prev_q: str, curr_q: str) -> bool:
    """Return True iff prev_q is the quarter immediately before curr_q (e.g. 2025Q3 before 2025Q4)."""
    import re
    m_curr = re.match(r"^(\d{4})Q([1-4])$", (curr_q or "").strip())
    m_prev = re.match(r"^(\d{4})Q([1-4])$", (prev_q or "").strip())
    if not m_curr or not m_prev:
        return False
    y, q = int(m_curr.group(1)), int(m_curr.group(2))
    if q >= 2:
        expected_prev = f"{y}Q{q - 1}"
    else:
        expected_prev = f"{y - 1}Q4"
    return (prev_q or "").strip() == expected_prev


def aggregate_holdings_by_cusip(holdings: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate holdings by CUSIP (or NO_CUSIP:{issuer} when CUSIP missing).
    Returns dict: key -> {issuer, value_usd_k, shares}.
    """
    agg: Dict[str, Dict[str, Any]] = {}
    for h in holdings:
        issuer = (h.get("issuer") or "").strip()
        if not issuer:
            continue
        cusip = h.get("cusip")
        key = (cusip and str(cusip).strip()) or f"NO_CUSIP:{issuer}"
        v_k = 0
        try:
            v_k = int(h.get("value_usd_k") or 0)
        except (TypeError, ValueError):
            pass
        sh = 0
        try:
            sh = int(h.get("shares") or 0)
        except (TypeError, ValueError):
            pass
        if key not in agg:
            agg[key] = {"issuer": issuer, "value_usd_k": v_k, "shares": sh, "cusip": cusip if (cusip and str(cusip).strip()) else None}
        else:
            agg[key]["value_usd_k"] += v_k
            agg[key]["shares"] += sh
    return agg


def aggregate_holdings(holdings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aggregate raw holdings by CUSIP (or NO_CUSIP:{issuer} when missing).
    Returns a list of one row per key with summed value_usd_k and shares, for use before weight/sort/write.
    """
    agg = aggregate_holdings_by_cusip(holdings)
    result: List[Dict[str, Any]] = []
    for key, v in agg.items():
        cusip_out = v.get("cusip") if not key.startswith("NO_CUSIP:") else None
        result.append({
            "issuer": v["issuer"],
            "cusip": cusip_out,
            "value_usd_k": v["value_usd_k"],
            "shares": v["shares"],
        })
    return result


def _quarter_sort_key(q: str) -> Tuple[int, int]:
    """Parse 2025Q4 -> (2025, 4) for sorting."""
    import re
    m = re.match(r"^(\d{4})Q([1-4])$", (q or "").strip())
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))


def get_prev_quarter_from_history(slug: str, quarter_now: str, out_dir: str) -> Optional[str]:
    """From data/13f/history/{slug}/ find the most recent quarter that is not quarter_now."""
    history_dir = os.path.join(out_dir, "history", slug)
    if not os.path.isdir(history_dir):
        return None
    quarters = []
    for f in os.listdir(history_dir):
        if f.endswith(".json"):
            q = f[:-5]
            if q and q != quarter_now:
                quarters.append(q)
    if not quarters:
        return None
    quarters.sort(key=_quarter_sort_key)
    return quarters[-1]


def _diff_item(key: str, issuer: str, cusip_val: Any, value_prev: int, value_now: int, weight_prev: float, weight_now: float, shares_prev: int, shares_now: int, action: str) -> Dict[str, Any]:
    return {
        "issuer": issuer,
        "cusip": cusip_val,
        "value_prev": value_prev,
        "value_now": value_now,
        "value_delta": value_now - value_prev,
        "weight_prev": round(weight_prev, 6),
        "weight_now": round(weight_now, 6),
        "weight_delta": round(weight_now - weight_prev, 6),
        "shares_prev": shares_prev,
        "shares_now": shares_now,
        "shares_delta": shares_now - shares_prev,
        "action": action,
    }


def build_movers_diff_payload(
    slug: str,
    name: str,
    quarter_now: str,
    filing_date_now: str,
    curr_data: Dict[str, Any],
    prev_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Build data/13f/diff/{slug}.json payload: counts + top_new, top_add, top_trim, top_exit."""
    prev_holdings = prev_data.get("holdings") or []
    curr_holdings = curr_data.get("holdings") or []
    prev_agg = aggregate_holdings_by_cusip(prev_holdings)
    curr_agg = aggregate_holdings_by_cusip(curr_holdings)
    total_prev = sum(v["value_usd_k"] for v in prev_agg.values()) or 1
    total_curr = sum(v["value_usd_k"] for v in curr_agg.values()) or 1

    counts: Dict[str, int] = {"new": 0, "add": 0, "trim": 0, "exit": 0}
    list_new: List[Dict[str, Any]] = []
    list_add: List[Dict[str, Any]] = []
    list_trim: List[Dict[str, Any]] = []
    list_exit: List[Dict[str, Any]] = []

    for key, curr in curr_agg.items():
        cusip_val = curr.get("cusip") if not key.startswith("NO_CUSIP:") else None
        v_curr = curr["value_usd_k"]
        s_curr = curr["shares"]
        w_curr = v_curr / total_curr
        if key not in prev_agg:
            counts["new"] += 1
            list_new.append(_diff_item(key, curr["issuer"], cusip_val, 0, v_curr, 0.0, w_curr, 0, s_curr, "NEW"))
        else:
            prev = prev_agg[key]
            v_prev = prev["value_usd_k"]
            s_prev = prev["shares"]
            w_prev = v_prev / total_prev
            delta_v = v_curr - v_prev
            if (s_curr > s_prev) or (v_curr > v_prev):
                counts["add"] += 1
                list_add.append(_diff_item(key, curr["issuer"], cusip_val, v_prev, v_curr, w_prev, w_curr, s_prev, s_curr, "ADD"))
            elif (s_curr < s_prev) or (v_curr < v_prev):
                counts["trim"] += 1
                list_trim.append(_diff_item(key, curr["issuer"], cusip_val, v_prev, v_curr, w_prev, w_curr, s_prev, s_curr, "TRIM"))

    for key, prev in prev_agg.items():
        if key not in curr_agg:
            counts["exit"] += 1
            cusip_val = prev.get("cusip") if not key.startswith("NO_CUSIP:") else None
            v_prev = prev["value_usd_k"]
            w_prev = v_prev / total_prev
            list_exit.append(_diff_item(key, prev["issuer"], cusip_val, v_prev, 0, w_prev, 0.0, prev["shares"], 0, "EXIT"))

    TOP_N = 20
    list_new.sort(key=lambda x: x["value_now"], reverse=True)
    list_add.sort(key=lambda x: x["value_delta"], reverse=True)
    list_trim.sort(key=lambda x: x["value_delta"], reverse=False)
    list_exit.sort(key=lambda x: x["value_prev"], reverse=True)

    return {
        "slug": slug,
        "name": name,
        "quarter_now": quarter_now,
        "quarter_prev": (prev_data.get("latest") or {}).get("quarter") or "",
        "filing_date_now": filing_date_now,
        "counts": counts,
        "lists": {
            "top_new": list_new[:TOP_N],
            "top_add": list_add[:TOP_N],
            "top_trim": list_trim[:TOP_N],
            "top_exit": list_exit[:TOP_N],
        },
    }


def write_history_snapshot(slug: str, out_dir: str) -> None:
    """Copy data/13f/{slug}.json to data/13f/history/{slug}/{quarter}.json (quarter from file)."""
    src = os.path.join(out_dir, f"{slug}.json")
    if not os.path.isfile(src):
        return
    try:
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    quarter = (data.get("latest") or {}).get("quarter") or ""
    if not quarter:
        return
    dest_dir = os.path.join(out_dir, "history", slug)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{quarter}.json")
    try:
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[history] {slug}/{quarter}.json")
    except OSError as e:
        print(f"[history] Failed {slug}/{quarter}: {e}")


def write_diff_for_slug(slug: str, out_dir: str) -> None:
    """Load current + prev from history, build diff payload, write data/13f/diff/{slug}.json."""
    curr_path = os.path.join(out_dir, f"{slug}.json")
    try:
        with open(curr_path, "r", encoding="utf-8") as f:
            curr_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    quarter_now = (curr_data.get("latest") or {}).get("quarter") or ""
    if not quarter_now:
        return
    prev_quarter = get_prev_quarter_from_history(slug, quarter_now, out_dir)
    if not prev_quarter:
        payload = {
            "slug": slug,
            "name": curr_data.get("name") or slug,
            "quarter_now": quarter_now,
            "quarter_prev": "",
            "filing_date_now": (curr_data.get("latest") or {}).get("filing_date") or "",
            "counts": {"new": 0, "add": 0, "trim": 0, "exit": 0},
            "lists": {"top_new": [], "top_add": [], "top_trim": [], "top_exit": []},
        }
    else:
        prev_path = os.path.join(out_dir, "history", slug, f"{prev_quarter}.json")
        try:
            with open(prev_path, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            payload = {
                "slug": slug,
                "name": curr_data.get("name") or slug,
                "quarter_now": quarter_now,
                "quarter_prev": "",
                "filing_date_now": (curr_data.get("latest") or {}).get("filing_date") or "",
                "counts": {"new": 0, "add": 0, "trim": 0, "exit": 0},
                "lists": {"top_new": [], "top_add": [], "top_trim": [], "top_exit": []},
            }
        else:
            payload = build_movers_diff_payload(
                slug,
                curr_data.get("name") or slug,
                quarter_now,
                (curr_data.get("latest") or {}).get("filing_date") or "",
                curr_data,
                prev_data,
            )
    diff_dir = os.path.join(out_dir, "diff")
    os.makedirs(diff_dir, exist_ok=True)
    diff_path = os.path.join(diff_dir, f"{slug}.json")
    tmp_path = diff_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, diff_path)
        print(f"[diff] {slug}.json")
    except OSError as e:
        print(f"[diff] Failed {slug}: {e}")


def compute_quarter_diff(
    prev_agg: Dict[str, Dict[str, Any]],
    curr_agg: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    """
    Compare aggregated prev vs current holdings by key (CUSIP-based).
    Returns (stats.changes dict, diffs list). change values: "NEW", "ADD", "TRIM", "EXIT" (uppercase).
    """
    changes: Dict[str, int] = {"new": 0, "add": 0, "trim": 0, "exit": 0}
    diffs: List[Dict[str, Any]] = []

    for key, curr in curr_agg.items():
        if key not in prev_agg:
            changes["new"] += 1
            diffs.append({
                "change": "NEW",
                "issuer": curr["issuer"],
                "value_delta_k": curr["value_usd_k"],
                "shares_delta": curr["shares"],
            })
        else:
            prev = prev_agg[key]
            delta_v = curr["value_usd_k"] - prev["value_usd_k"]
            delta_s = curr["shares"] - prev["shares"]
            if curr["shares"] > prev["shares"]:
                changes["add"] += 1
                diffs.append({
                    "change": "ADD",
                    "issuer": curr["issuer"],
                    "value_delta_k": delta_v,
                    "shares_delta": delta_s,
                })
            elif curr["shares"] < prev["shares"]:
                changes["trim"] += 1
                diffs.append({
                    "change": "TRIM",
                    "issuer": curr["issuer"],
                    "value_delta_k": delta_v,
                    "shares_delta": delta_s,
                })
            # else: equal shares, skip (no diff entry)

    for key, prev in prev_agg.items():
        if key not in curr_agg:
            changes["exit"] += 1
            diffs.append({
                "change": "EXIT",
                "issuer": prev["issuer"],
                "value_delta_k": -prev["value_usd_k"],
                "shares_delta": -prev["shares"],
            })

    diffs.sort(key=lambda x: abs(x.get("value_delta_k") or 0), reverse=True)
    return changes, diffs

def build_index_payload(staged_slugs: List[str], out_dir: str) -> Dict[str, Any]:
    """
    Build data/13f/index.json payload from the just-promoted per-slug JSON files.
    Keeps list stable: one entry per staged slug (placeholder on read failure).
    """
    now_utc = datetime.utcnow().isoformat() + "Z"
    managers: List[Dict[str, str]] = []

    for slug in staged_slugs:
        name = slug
        latest_quarter = ""
        filing_date = ""

        p = os.path.join(out_dir, f"{slug}.json")
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            name = d.get("name") or slug
            latest = d.get("latest") or {}
            latest_quarter = latest.get("quarter") or ""
            filing_date = latest.get("filing_date") or ""
        except (OSError, json.JSONDecodeError):
            # Keep placeholders to avoid breaking list length/order
            pass

        managers.append(
            {
                "slug": slug,
                "name": name,
                "latest_quarter": latest_quarter,
                "filing_date": filing_date,
            }
        )

    return {"updated_at_utc": now_utc, "managers": managers}

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
        prev_data: Optional[Dict[str, Any]] = None
        prev_path = os.path.join(OUT_DIR, f"{slug}.json")
        if os.path.isfile(prev_path):
            try:
                with open(prev_path, "r", encoding="utf-8") as f:
                    prev_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                prev_data = None
        if prev_data is not None:
            if not isinstance(prev_data.get("holdings"), list) or not (prev_data.get("latest") or {}).get("quarter"):
                prev_data = None

        sub = fetch_json(SUBMISSIONS.format(cik.zfill(10)))
        recent = sub.get("filings", {}).get("recent", {})

        latest, previous_filing = pick_latest_and_previous_13f(recent)
        if not latest:
            print(f"[{slug}] No 13F-HR found with primaryDocument.")
            continue

        acc = latest["accessionNumber"]
        filing_date = latest.get("filingDate") or ""
        report_date = latest.get("reportDate") or ""
        quarter = _quarter_from_filing(latest)

        infotable_url, infotable_fname = find_infotable_from_index(cik, acc)
        print(f"[{slug}] Fetching infotable (latest): {infotable_url}")

        xml_bytes, _ = fetch_bytes(infotable_url)
        raw_holdings = parse_infotable_xml(xml_bytes)
        holdings = aggregate_holdings(raw_holdings)

        total_value = sum(h["value_usd_k"] for h in holdings) or 1
        for h in holdings:
            h["weight"] = round(h["value_usd_k"] / total_value, 6)

        holdings_sorted = sorted(holdings, key=lambda x: x["value_usd_k"], reverse=True)
        top1 = holdings_sorted[0]["issuer"] if holdings_sorted else None

        if previous_filing:
            quarter_prev = _quarter_from_filing(previous_filing)
            if quarter_prev and quarter_prev != quarter:
                prev_history_dir = os.path.join(OUT_DIR, "history", slug)
                prev_history_path = os.path.join(prev_history_dir, f"{quarter_prev}.json")
                skip_prev = os.path.isfile(prev_history_path)
                if not skip_prev:
                    acc_prev = previous_filing["accessionNumber"]
                    try:
                        infotable_url_prev, _ = find_infotable_from_index(cik, acc_prev)
                        print(f"[{slug}] Fetching infotable (previous {quarter_prev}): {infotable_url_prev}")
                        xml_bytes_prev, _ = fetch_bytes(infotable_url_prev)
                        raw_prev = parse_infotable_xml(xml_bytes_prev)
                        holdings_prev = aggregate_holdings(raw_prev)
                        total_prev = sum(h["value_usd_k"] for h in holdings_prev) or 1
                        for h in holdings_prev:
                            h["weight"] = round(h["value_usd_k"] / total_prev, 6)
                        holdings_prev_sorted = sorted(holdings_prev, key=lambda x: x["value_usd_k"], reverse=True)
                        top1_prev = holdings_prev_sorted[0]["issuer"] if holdings_prev_sorted else None
                        prev_out = {
                            "name": sub.get("name") or slug,
                            "latest": {
                                "quarter": quarter_prev,
                                "filing_date": previous_filing.get("filingDate") or "",
                                "infotable_url": infotable_url_prev,
                            },
                            "stats": {
                                "holdings": len(holdings_prev_sorted),
                                "top1": top1_prev,
                                "changes": {"new": 0, "add": 0, "trim": 0, "exit": 0},
                            },
                            "holdings": [
                                {"issuer": h["issuer"], "value_usd_k": h["value_usd_k"], "weight": h["weight"], "shares": h["shares"], "cusip": h.get("cusip")}
                                for h in holdings_prev_sorted
                            ],
                            "updated_at": datetime.utcnow().isoformat() + "Z",
                        }
                        os.makedirs(prev_history_dir, exist_ok=True)
                        tmp_path = prev_history_path + ".tmp"
                        with open(tmp_path, "w", encoding="utf-8") as f:
                            json.dump(prev_out, f, ensure_ascii=False, indent=2)
                        os.replace(tmp_path, prev_history_path)
                        print(f"[history] {slug}/{quarter_prev}.json (previous)")
                    except Exception as e:
                        print(f"[{slug}] Failed to fetch/write previous {quarter_prev}: {e}")
                else:
                    print(f"[{slug}] Skipping previous {quarter_prev} (already exists)")

        changes_counts: Dict[str, int] = {"new": 0, "add": 0, "trim": 0, "exit": 0}
        diffs_list: List[Dict[str, Any]] = []
        if prev_data is not None:
            prev_quarter = (prev_data.get("latest") or {}).get("quarter")
            if prev_quarter and is_previous_quarter(prev_quarter, quarter):
                prev_holdings = prev_data.get("holdings") or []
                prev_agg = aggregate_holdings_by_cusip(prev_holdings)
                curr_agg = aggregate_holdings_by_cusip(holdings_sorted)
                changes_counts, diffs_list = compute_quarter_diff(prev_agg, curr_agg)

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
                "changes": changes_counts,
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
        if diffs_list:
            out["diffs"] = diffs_list

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

    for slug in staged_slugs:
        write_history_snapshot(slug, OUT_DIR)

    for slug in staged_slugs:
        write_diff_for_slug(slug, OUT_DIR)

    if staged_slugs:
        try:
            payload = build_index_payload(staged_slugs, OUT_DIR)
            index_path = os.path.join(OUT_DIR, "index.json")
            tmp_index_path = index_path + ".tmp"
            with open(tmp_index_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_index_path, index_path)
            print(f"[index] Wrote {index_path} ({len(payload.get('managers') or [])} managers)")
        except OSError as e:
            print(f"[index] Failed to write index.json: {e}")
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    print(f"Promoted {len(staged_slugs)} files to data/13f")
if __name__ == "__main__":
    main()