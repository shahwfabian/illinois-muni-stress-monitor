# Windows without make: run the python commands directly.
PY ?= python
export PYTHONPATH := src

run:      ## full pipeline (idempotent, single command)
	$(PY) -m muni_monitor.pipeline
offline:  ## reuse cached Treasury CSVs, no network
	$(PY) -m muni_monitor.pipeline --offline
test:
	$(PY) -m pytest -q
app:
	$(PY) -m streamlit run app/streamlit_app.py
static:   ## rebuild the Vercel static site from the database
	$(PY) scripts/build_static.py
notebook: ## regenerate + execute the validation notebook
	$(PY) scripts/make_notebook.py
