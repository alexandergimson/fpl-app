PYTHON ?= python3
CSV ?=

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

ingest-underlying:
	$(PYTHON) -m scripts.ingest_underlying $(CSV)

ingest-team-underlying:
	$(PYTHON) -m scripts.ingest_team_underlying $(CSV)

price-par:
	$(PYTHON) -m scripts.show_price_par

backtest:
	$(PYTHON) -m scripts.backtest

snapshot-tracked:
	$(PYTHON) -m scripts.snapshot_tracked

generate-alerts:
	$(PYTHON) -m scripts.generate_alerts

test:
	$(PYTHON) -m unittest discover -s tests

dev:
	.venv/bin/python -m uvicorn backend.api.main:app --reload
