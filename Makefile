PYTHON ?= python3

.PHONY: setup init-db ingest price-par backtest test dev

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install -r requirements.txt

init-db:
	$(PYTHON) -m scripts.init_db

ingest:
	$(PYTHON) -m scripts.ingest_historical

ingest-current:
	$(PYTHON) -m scripts.ingest_current

price-par:
	$(PYTHON) -m scripts.show_price_par

backtest:
	$(PYTHON) -m scripts.backtest

test:
	$(PYTHON) -m unittest discover -s tests

dev:
	.venv/bin/python -m uvicorn backend.api.main:app --reload
