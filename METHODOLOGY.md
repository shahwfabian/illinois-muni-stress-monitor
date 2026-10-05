# Methodology

## Conventions
* Munis: 30/360 (US), semiannual, street-convention yield. Treasuries: ACT/ACT. Prices per 100 par.
* Settlement: T+2 before 2024-05-28, T+1 after; business days only (no holiday calendar).
* Yields used are the **reoffering yields in issuer Official Statements** (`NEW_ISSUE` records, priced on the pricing date) and, when supplied, **EMMA trade yields**. Settlement is approximated as pricing date + T+1 (delivery is usually ~2 weeks later; the effect on spread is negligible).

## Treasury benchmark
Par curve for the last available date on or before the trade date (max 5 calendar days back, else the trade is dropped and counted in the `treasury_alignment` check). Interpolated at the bond's years-to-settlement-maturity with **PCHIP (monotone cubic)**: it hits every knot and cannot overshoot on flat or inverted curves. No extrapolation; maturities outside 1M to 30Y are dropped.

## Spread and ratio
`spread_bps = (muni yield - interpolated Treasury par yield) x 10,000`; `ratio = muni yield / Treasury yield`. Compared on a nominal, pre-tax basis: for tax-exempt bonds a ratio below 100% is normal and the ratio (not the raw spread) is the tax-adjusted view. Tax-equivalent yield = `y / (1 - (federal + state))` with federal brackets 22 to 37% and no federal deduction of state tax. Only bonds flagged `tax_exempt` get a TEY. **The Illinois rate (4.95%) is applied only when a bond is flagged `il_exempt`.** Every State of Illinois GO and CPS Official Statement parsed here states that interest is *not exempt from Illinois income taxes*, so for these bonds the TEY is federal-only.

## Trade filtering
**Callable bonds**: bonds marked in the Official Statement as priced to a call date (`is_callable=1`) are excluded, because that yield is not comparable to a maturity-matched Treasury.

Excluded from spread analytics: odd lots (par < $100k), price outliers (per-CUSIP median/MAD robust z > 6, needs >= 5 trades), impossible yields (<= 0, > 15%, missing). Inter-dealer trades are flagged but **kept**, since they are large and informative; filter by `is_interdealer` to test sensitivity. Exact duplicates are dropped.

## Spread series
Issuer series use the median spread of **tax-exempt bonds in the 7-12y bucket** per pricing/trade date. A fixed bucket stops the maturity mix of each deal from moving the series; excluding taxable bonds (e.g. Illinois 2024A) keeps the spreads comparable, since a taxable bond's nominal spread is not comparable to an exempt bond's.

## Stress score (0 to 100, higher = more stress)
| Component | Weight | Definition | Why |
|---|---|---|---|
| Spread level | 50% | 20-obs rolling mean of issuer median spread, linear from 0 bp (0) to 300 bp (100), clipped | The market's direct price of credit risk; the largest weight because it is the only forward-looking input |
| Spread change | 20% | Latest median spread minus the value 20 observations earlier, -50 bp (0) to +50 bp (100) | Captures deterioration or improvement independent of level |
| Pension | 30% | 100 minus latest funded ratio (%), clipped to 0..100 | Structural, slow-moving liability pressure; lower weight because it is annual and lagged |

The 300 bp and +/-50 bp anchors and the 50/20/30 weights are **judgment calls**, not estimated parameters; they are stated so they can be challenged and changed in `stress.py`. Missing components are dropped and the remaining weights rescaled pro rata; this is noted per issuer. The pension figure is the unweighted mean of plan funded ratios for the latest fiscal year (a simplification; liability-weighting is better when data allows). "Observations" are trade days with data, not calendar days.

## Limitations
* This is **not the MMD curve** or any evaluated-pricing benchmark; it is a Treasury-relative spread from raw trades.
* Muni trade data is sparse and noisy; medians per day can rest on one trade. `n_trades` is stored, show it.
* Spreads reflect **liquidity, call features, tax-status and supply** as well as credit. Callable bonds quoted at yield-to-call are not comparable to maturity-matched Treasuries.
* Par-yield interpolation on a par curve is an approximation for bonds with coupons far from par.
* Sample is small and not random (whole deals, not a chosen 5 to 10 bonds). City of Chicago GO has no bonds loaded.
* Current data is primary-market (new-issue) pricing: includes underwriter concession, and only a handful of dates.
* Events are annotations, not causal claims.
