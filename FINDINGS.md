# Findings (research note)

All figures come from the pipeline database built from issuer Official Statements, Public Plans Data and Treasury.gov. **Sample is small and primary-market only (new-issue reoffering yields, not secondary trades), so conclusions are tentative.**

## Data
* 96 bonds with CUSIPs parsed from five Official Statements: State of Illinois (Refunding Series Oct 2024; Series Oct 2024A/B/C) and Chicago Public Schools (Series 2023A, 2025A, 2025B/C). 86 are federally tax-exempt; 10 (Illinois 2024A) are taxable. All state they are **not exempt from Illinois income tax**.
* 65 bonds are usable for spread analysis; 31 are excluded because they are priced to a call date (yield not comparable to a maturity-matched Treasury).
* City of Chicago GO: no official statement could be retrieved, so Chicago has pension data only and no spread.

## What the data shows (tax-exempt bonds, 7-12 year bucket, reoffering yield vs interpolated Treasury par yield)
| Issuer | Pricing date | Bonds | Avg yield | Avg Treasury | Spread | Muni/UST ratio |
|---|---|---|---|---|---|---|
| CPS | 2023-10-26 | 5 | 5.24% | 4.86% | +38 bp | 108% |
| CPS | 2025-10-28 | 8 | 4.57% | 3.89% | +68 bp | 118% |
| State of Illinois | 2024-09-10 | 3 | 3.23% | 3.59% | -36 bp | 90% |
| State of Illinois | 2024-09-17 | 3 | 3.10% | 3.57% | -47 bp | 87% |

* **CPS prices at a clear premium to Treasuries (ratio above 100%) and the premium widened by about 30 bp between the two deals.** A tax-exempt bond yielding more than a taxable Treasury is unusual and points to credit and/or liquidity compensation.
* **State of Illinois priced inside Treasuries in nominal terms** (ratio 87 to 90%), despite pension funded ratios near 46%. (Exempt yields normally sit below taxable yields because of the tax benefit, so the ratio, not the raw spread, is the fair comparison.)
* Pension funded ratios (FY2024, Public Plans Data): Illinois SERS 45.8%, TRS 45.8%, SURS 46.0%; Chicago Municipal 25.8%, Fire 24.4%, Laborers 42.6%; Chicago Teachers (CTPF) 48.1%.
* Composite stress scores (0 to 100): CPS 30, Illinois 20; the change component is unavailable (too few observations), so those scores are reweighted.

## Interpretation and caveats
* Pension funded ratio does **not** explain the ordering across these issuers: Illinois and CTPF funded ratios are similar (46 to 48%), yet CPS's muni/Treasury ratio is roughly 30 percentage points higher. Something other than pension funding must explain the gap; this project does not test what (ratings, security structure and budget position are candidates). With two issuers and four pricing events this cannot be tested statistically; the result is **suggestive, not conclusive**.
* Four pricing dates do not make a time series. Rolling averages and z-scores need secondary-market trades (EMMA CSVs, which must be downloaded manually; see DATA_SOURCES.md).
* New-issue yields include underwriter concession and reflect a single day's market, and different maturities were sold in each deal. This is not the MMD curve.
