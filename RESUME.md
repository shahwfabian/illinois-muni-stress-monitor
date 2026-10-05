# Resume point

**Project line (one line, fits under a Projects heading)**
> **Illinois Municipal Credit & Pension Stress Monitor** | Python, SQLite, pandas, SciPy, Streamlit, pytest | github.com/shahwfabian/illinois-muni-stress-monitor

**Bullets (pick 2 to 3)**
* Built an end-to-end fixed income pipeline that parses CUSIPs, coupons, maturities and reoffering yields for 96 State of Illinois and Chicago Public Schools GO bonds from issuer Official Statements, joins them to the U.S. Treasury par curve (cross-checked to FRED to 0.0 bp), and loads a documented SQLite schema with logged data-quality checks (11 checks, one-command idempotent rerun).
* Implemented bond analytics from first principles (30/360 and ACT/ACT pricing, yield solver, Macaulay/modified duration, convexity, DV01, PCHIP curve interpolation, spread-to-Treasury, muni/Treasury ratio, tax-equivalent yield) and verified against closed-form values and finite differences in 27 unit/integration tests and a validation notebook, with CI on GitHub Actions.
* Constructed a transparent, weighted credit stress score combining Treasury spreads and FY2024 pension funded ratios (Public Plans Data), and found CPS's tax-exempt 7-12y spread widened from about +38 bp to +68 bp between its Oct 2023 and Oct 2025 deals while Illinois GO priced inside Treasuries; reported honestly as suggestive given a small primary-market sample.
* Caught and fixed a tax-treatment error by reading the Official Statements (Illinois and CPS interest is not exempt from Illinois income tax), and excluded yield-to-call bonds that are not comparable to maturity-matched Treasuries.

**Interview talking points**
* Why spread is compared as a muni/Treasury *ratio* for exempt bonds, and why PCHIP over a natural spline.
* Why this is not the MMD curve, why new-issue yields include underwriter concession, and what secondary-market EMMA trades would add (the pipeline already ingests them).
* The stress-score weights (50/20/30) and caps are judgment calls, stated in METHODOLOGY.md, and open to challenge.

**Say plainly if asked:** data is primary-market (new-issue) pricing, not secondary trades; City of Chicago GO bonds are not loaded; it is an educational project on public data.
