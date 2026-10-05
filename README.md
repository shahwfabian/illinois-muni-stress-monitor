# Illinois Municipal Credit & Pension Stress Monitor

**Question:** how much extra yield does the market demand from State of Illinois GO, City of Chicago GO and Chicago Public Schools bonds over the U.S. Treasury curve, and does that move with the health of their pension systems?

Python 3.11+ · pandas · numpy · scipy · SQLite · Streamlit · pytest. All data is public; findings are for educational purposes only, not investment advice.

## Status
* **Real data loaded:** 96 CUSIPs with coupons, maturities and reoffering yields parsed from issuer Official Statements (State of Illinois GO, CPS), Treasury par curve (cross-checked to FRED), FY2024 pension funded ratios (Public Plans Data).
* **Honest limits:** spreads are primary-market (new issue), not secondary trades, because EMMA blocks automated access (drop CSVs into `data/manual/` and rerun). City of Chicago GO bonds are not loaded (no retrievable Official Statement). See [FINDINGS.md](FINDINGS.md), [DATA_SOURCES.md](DATA_SOURCES.md).
* 27 tests, GitHub Actions CI, validation notebook. Resume wording: [RESUME.md](RESUME.md).

## Run
```bash
pip install -r requirements.txt
python -m muni_monitor.pipeline        # PYTHONPATH=src ; idempotent, one command (make run)
python -m pytest -q                    # make test
streamlit run app/streamlit_app.py     # make app
python scripts/build_static.py         # rebuild web/ for Vercel
```
Set `PYTHONPATH=src` (the Makefile does).

## Layout
`src/muni_monitor/` analytics, etl, quality, stress, treasury, pipeline · `app/` Streamlit · `web/` static dashboard (Vercel) · `notebooks/validation.ipynb` · [SCHEMA.md](SCHEMA.md) · [METHODOLOGY.md](METHODOLOGY.md)

Live dashboard: https://muni-stress-monitor.vercel.app
