# Illinois Municipal Credit & Pension Stress Monitor

**Question:** how much extra yield does the market demand from State of Illinois GO, City of Chicago GO and Chicago Public Schools bonds over the U.S. Treasury curve, and does that move with the health of their pension systems?

Python 3.11+ · pandas · numpy · scipy · SQLite · Streamlit · pytest. All data is public; findings are for educational purposes only, not investment advice.

## Status (be aware)
* Live and verified: Treasury par curve ETL (cross-checked to FRED), SQLite schema, data-quality checks, first-principles analytics engine (22 tests, validation notebook), stress-score engine, Streamlit app and static dashboard.
* **Not loaded:** muni trades, bond CUSIPs and pension figures. EMMA prohibits automated access (HTTP 403 observed), and I did not invent identifiers. Follow [DATA_SOURCES.md](DATA_SOURCES.md) to supply them; until then muni panels show empty states. See [FINDINGS.md](FINDINGS.md).

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

Live static dashboard: see the repository's Vercel deployment.
