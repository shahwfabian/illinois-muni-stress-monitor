"""Extract maturity schedules (CUSIP, coupon, maturity, reoffering yield, price) from official
statements (PDF text from `pdftotext -raw`) into data/manual/securities.csv and
data/manual/new_issue_pricing.csv.

Everything is parsed from issuer-published Official Statements; nothing is typed by hand except
the per-document metadata in DOCS (pricing date, series tax status, source URL), each read from
the document itself. Re-run with `python scripts/parse_os.py` after `pdftotext -raw`.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OS_DIR = ROOT / "data" / "raw" / "os"
OUT = ROOT / "data" / "manual"

# series -> federal tax-exempt? (from each document's cover/tax-matters text). Illinois income tax:
# every document states interest is NOT exempt from Illinois income taxes.
DOCS = [
    dict(file="il_2024_10_ref", issuer="IL_GO", prefix="452153", price_date="2024-09-10",
         exempt={"": 1}, url="https://capitalmarkets.illinois.gov/content/dam/soi/en/web/capitalmarkets/documents/recent-bond-sales/State%20of%20Illinois,%20Refunding%20Series%20of%20October%202024%20Official%20Statement.pdf"),
    dict(file="il_2024_10_abc", issuer="IL_GO", prefix="452153", price_date="2024-09-17",
         exempt={"2024A": 0, "2024B": 1, "2024C": 1}, url="https://capitalmarkets.illinois.gov/content/dam/soi/en/web/capitalmarkets/documents/official-statements/2024/State%20of%20Illinois%2C%20Taxable%20Series%20of%20October%202024A%20and%20Series%20of%20October%202024BC%20Official%20Statement.pdf"),
    dict(file="cps_2023a", issuer="CPS", prefix="", price_date="2023-10-26", exempt={"": 1},
         url="https://www.cps.edu/globalassets/cps-pages/about-cps/finance/official-statements-for-long-term-bonds/series-2023a-final-os-2023-10-26.pdf"),
    dict(file="cps_2025a", issuer="CPS", prefix="", price_date="2025-09-11", exempt={"": 1},
         url="https://www.cps.edu/globalassets/cps-pages/about-cps/finance/official-statements-for-long-term-bonds/official-statement---series-2025a.pdf"),
    dict(file="cps_2025bc", issuer="CPS", prefix="", price_date="2025-10-28", exempt={"": 1},
         url="https://www.cps.edu/globalassets/cps-pages/about-cps/finance/official-statements-for-long-term-bonds/final-offical-statement---cps-series-2025bc---2025-11-07.pdf"),
]

IL_ROW = re.compile(r"^(\d{4}) \$?([\d,]+) ([\d.]+)% ([\d.]+)%(\*\*)? ([\d.]+) ([A-Z0-9]{3})$")
CPS_ROW = re.compile(r"^(\d{4}) (?:\$ )?([\d,]+) ([\d.]+) ([\d.]+) ([\d.]+)(\*)? (167505[A-Z0-9]{3})$")
CPS_TERM = re.compile(r"^\$([\d,]+) ([\d.]+)% Term Bonds due (\w+) (\d+), (\d{4}), Yield ([\d.]+)%, Price ([\d.]+)%\*? CUSIP (167505[A-Z0-9]{3})")
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                      "August", "September", "October", "November", "December"], 1)}


def parse(doc: dict) -> list[dict]:
    lines = (OS_DIR / f"{doc['file']}.raw.txt").read_text(encoding="utf-8", errors="ignore").splitlines()
    rows, series, month = [], "", None
    for i, ln in enumerate(lines[:400]):
        ln = ln.strip()
        m = re.search(r"Series of October (\d{4}[A-C]+)\b", ln)
        if m and doc["issuer"] == "IL_GO" and ln.startswith("$"):
            series = m.group(1)
        if ln in ("Due", "Maturity") and i + 1 < len(lines):
            mm = re.match(r"(\w+) (\d+)", lines[i + 1].strip())
            if mm and mm.group(1) in MONTHS:
                month = (MONTHS[mm.group(1)], int(mm.group(2)))
        if doc["issuer"] == "IL_GO" and re.match(r"^\$[\d,]+ General Obligation Bonds", ln):
            sm = re.search(r"Series of (?:October )?(\d{4}[A-C]*)", ln)
            series = sm.group(1) if sm else ""
        r = IL_ROW.match(ln) if doc["issuer"] == "IL_GO" else CPS_ROW.match(ln)
        if r and month:
            if doc["issuer"] == "IL_GO":
                yr, amt, cpn, yld, star, px, suf = r.groups()
                cusip = doc["prefix"] + suf
            else:
                yr, amt, cpn, yld, px, star, cusip = r.groups()
            rows.append(dict(cusip=cusip, series=series, maturity=f"{yr}-{month[0]:02d}-{month[1]:02d}",
                             coupon=float(cpn), yield_pct=float(yld), price=float(px),
                             par=int(amt.replace(",", "")), call_basis=int(bool(star))))
        t = CPS_TERM.match(ln)
        if t:
            amt, cpn, mon, day, yr, yld, px, cusip = t.groups()
            rows.append(dict(cusip=cusip, series=series, maturity=f"{yr}-{MONTHS[mon]:02d}-{int(day):02d}",
                             coupon=float(cpn), yield_pct=float(yld), price=float(px),
                             par=int(amt.replace(",", "")), call_basis=0))
    return rows


def main() -> None:
    sec, px, seen = [], [], set()
    for d in DOCS:
        for r in parse(d):
            if r["cusip"] in seen:
                continue
            seen.add(r["cusip"])
            ex = d["exempt"].get(r["series"], d["exempt"].get("", 1))
            sec.append(dict(cusip=r["cusip"], issuer_key=d["issuer"],
                            description=f"{d['file']} {r['series']}".strip(), coupon=r["coupon"],
                            maturity_date=r["maturity"], tax_exempt=ex, il_exempt=0,
                            is_callable=r["call_basis"], call_date="", source_doc_url=d["url"]))
            px.append(dict(cusip=r["cusip"], trade_date=d["price_date"], trade_time="", price=r["price"],
                           yield_=r["yield_pct"], par_amount=r["par"], trade_type="NEW_ISSUE"))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "securities.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sec[0])); w.writeheader(); w.writerows(sec)
    with open(OUT / "new_issue_pricing.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cusip", "trade_date", "trade_time", "price", "yield", "par_amount", "trade_type"])
        w.writeheader()
        for r in px:
            r = dict(r); r["yield"] = r.pop("yield_"); w.writerow(r)
    by = {}
    for s in sec:
        by[s["issuer_key"]] = by.get(s["issuer_key"], 0) + 1
    print(f"parsed {len(sec)} bonds: {by}")


if __name__ == "__main__":
    main()
