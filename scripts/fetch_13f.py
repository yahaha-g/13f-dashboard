import json
import urllib.request
from datetime import datetime

CIKS = {
    "berkshire": "0001067983",
    "bridgewater": "0001350694",
    "himalaya": "0001603466",
    "hh": "0001848853"
}

BASE = "https://data.sec.gov/submissions/CIK{}.json"

USER_AGENT = "13f-dashboard (your@email.com)"

def fetch_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "identity"
        }
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    for name, cik in CIKS.items():
        url = BASE.format(cik.zfill(10))
        data = fetch_json(url)

        out = {
            "name": name,
            "latest_filing": data["filings"]["recent"]["accessionNumber"][0],
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }

        with open(f"data/13f/{name}.json", "w") as f:
            json.dump(out, f, indent=2)

        print(f"Updated {name}")

if __name__ == "__main__":
    main()
