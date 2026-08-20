# FPL Analytics

Local-first Fantasy Premier League analytics for valuing players against position and current-price benchmarks.

## Quick Start

```bash
make setup
make ingest
make price-par
make test
```

The app uses SQLite at `backend/data/fpl.sqlite`.

## Commands

```bash
make setup      # create a local venv and install Python deps
make init-db    # create SQLite schema
make ingest     # ingest 2025/26 historical players, gameweeks and Price Par prior
make ingest-current # ingest current official FPL bootstrap and fixtures
make price-par  # print stored Price Par curves
make backtest   # show walk-forward backtest scaffold
make test       # run stdlib unit tests
make dev        # run FastAPI after setup
```

## Data Sources

- Historical data: `vaastav/Fantasy-Premier-League` raw CSV files.
- Current data: official FPL API provider stub at `https://fantasy.premierleague.com/api/bootstrap-static/`.

The ingestion layer uses provider classes so future xG/xA/team-strength sources can be added without rewriting the modelling layer.
