# SQLite schema (`data/monitor.db`)

Defined in `src/muni_monitor/db.py`. Every load replaces its table, so reruns are idempotent (trade IDs are content hashes).

| Table | Key | Purpose |
|---|---|---|
| `issuers` | issuer_key | IL_GO, CHI_GO, CPS and their pension plans |
| `securities` | cusip | coupon, maturity, tax_exempt, is_callable, call_date, source_doc_url |
| `trades` | trade_id | Cleaned trades plus flags `is_odd_lot`, `is_interdealer`, `is_outlier`, `is_impossible_yield` |
| `treasury_curve` | (date, tenor_label) | Par yields in percent, long format, `tenor_years` numeric |
| `pension_metrics` | (issuer_key, plan, fiscal_year) | funded ratio, unfunded liability, employer contribution, source URL |
| `events` | (event_date, issuer_key, label) | User-supplied annotations |
| `trade_metrics` | trade_id | Per-trade yield, matched Treasury yield, spread (bp), ratio, modified duration, convexity, DV01, bucket, curve_date used |
| `issuer_spread_series` | (issuer_key, date) | Median spread, n trades, 20-obs rolling mean, 60-obs z-score |
| `stress_scores` | issuer_key | Latest component scores and composite |
| `dq_results` | run_ts, check_name | Data-quality results per run |
