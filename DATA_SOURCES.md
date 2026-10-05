# Data Sources (Phase 0 reconnaissance)

Probes run 2026-09-30. Status reflects what was actually tested.

| Source | URL | Fields | Frequency | Terms / access | Status |
|---|---|---|---|---|---|
| U.S. Treasury daily par yield curve | https://home.treasury.gov/resource-center/data-chart-center/interest-rates | 1M to 30Y par yields (bond-equivalent) | Daily, business days | U.S. government work, public domain; CSV endpoint by year | **Automated. Working** (12,573 tenor-rows loaded, 2023 to date) |
| FRED Treasury series (DGS2, DGS10, DGS30) | https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10 | Constant-maturity yields | Daily | Public CSV download, no key | **Automated cross-check.** Max difference vs Treasury.gov: 0.0 bp over 2,805 points |
| MSRB EMMA trade data | https://emma.msrb.org | CUSIP, trade date/time, price, yield, par, trade type | Real time | EMMA terms restrict automated access; an unauthenticated request to `robots.txt` returned HTTP 403. **No scraping.** | **Manual CSV ingest** (below) |
| Public Plans Data | https://publicplansdata.org | Funded ratio, actuarial liabilities, ARC/contributions by plan and FY | Annual | Free, downloadable; check citation terms on site | **Manual CSV ingest** (not verified in this run) |
| Issuer ACFRs / actuarial reports | State Comptroller, City of Chicago Comptroller, CPS Finance, plan websites | Funded ratios, unfunded liability, contributions | Annual | Public documents | **Manual entry** with `source_url` per row |
| Official Statements (bond CUSIPs, coupons, maturities) | EMMA official statements (view manually) | CUSIP, coupon, maturity, call features, tax status | Per issue | Reading OS documents in a browser is fine; automated bulk download is not | **Manual entry** |

## What you need to supply (the pipeline runs without it, panels stay empty)

1. **`data/manual/securities.csv`** (copy `securities.template.csv`): 5 to 10 bonds per issuer across maturities (issuer keys `IL_GO`, `CHI_GO`, `CPS`). Take CUSIP, coupon, maturity, call date and tax status from each bond's Official Statement. Coupons may be `5.0` or `0.05`. Set `tax_exempt` to yes/no per bond (CPS and Chicago have taxable issues; do not assume).
2. **`data/manual/trades_<cusip or batch>.csv`** (any file named `trades*.csv`): on EMMA open each CUSIP's page, Trade Activity tab, use the export/download button. Required columns after header normalisation: `cusip, trade_date, price, yield, par_amount, trade_type` (`trade_time` optional). EMMA's export may omit CUSIP; add it as a column. Header aliases are in `etl.TRADE_ALIASES`; unknown headers fail loudly so nothing is guessed. Trade types accepted: sale to customer, purchase from customer, inter-dealer.
3. **`data/manual/pension_metrics.csv`**: `issuer_key, plan, fiscal_year, funded_ratio_pct, unfunded_liability, employer_contribution, source_url`.
4. **`data/manual/events.csv`** (optional): `event_date, issuer_key, label, source`. Only events you supply or cite.

Then run `python -m muni_monitor.pipeline`.

## Gaps (stated honestly)

* **Loaded from official documents (October 2026 update):** 96 CUSIPs from five issuer-published Official Statements (State of Illinois Capital Markets Office; CPS Finance), parsed by `scripts/parse_os.py` with reoffering yields as `NEW_ISSUE` records; FY2024 funded ratios for seven plans from Public Plans Data.
* **City of Chicago GO: no Official Statement could be retrieved**, so there are no Chicago bonds. Chicago Police Pension is not shown on the Public Plans Data page and is omitted.
* **No secondary-market trades are loaded** (EMMA blocks automation); spreads are primary-market only.
* Pension data is a single fiscal year; unfunded liability and contribution columns are blank.
* EMMA's exact export headers were not verified (blocked to automation); the alias map is a best effort and errors out on mismatch.
* Callable bonds: EMMA's yield may be yield-to-call or to-worst, which is not comparable to a maturity-matched Treasury. Record `is_callable` and `call_date`; see METHODOLOGY.md.
