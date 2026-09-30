# Findings (research note)

**Status: inconclusive on the core question. No municipal trade or pension data has been loaded.**

## What was measured (from pipeline output, 2026-09-30 run)
* Treasury benchmark loaded from home.treasury.gov for 2023 through 2026-09-29 (12,573 tenor observations). It matches FRED (DGS2/10/30) with a maximum difference of 0.0 bp over 2,805 comparisons.
* Par curve on 2026-09-29: 2Y 4.89%, 5Y 5.06%, 10Y 5.26%, 30Y 5.59%. The 2s10s slope is +37 bp (upward sloping). The 10Y is at the sample high for 2023 to date (low: 3.30% on 2023-04-06).

## What this project cannot yet say
* Whether Illinois, Chicago or CPS spreads are wide, tightening or stressed relative to pension funding. That requires the bond sample and EMMA trade CSVs (DATA_SOURCES.md) and pension data, which must be supplied manually because EMMA blocks automated access.
* No stress scores, spreads, ratios or z-scores exist. The dashboard shows empty states rather than placeholder values.

## Next step
Populate `data/manual/`, run `python -m muni_monitor.pipeline`, and regenerate this note from the resulting `stress_scores` and `issuer_spread_series` tables. Interpret with the limitations in METHODOLOGY.md (not MMD; sparse trades; liquidity mixed with credit).
