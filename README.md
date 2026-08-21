# FPL Analytics

Local-first Fantasy Premier League analytics for valuing players against position and current-price benchmarks.

## Quick Start

```bash
make setup
make ingest
make ingest-current
make price-par
make test
```

The app uses SQLite at `backend/data/fpl.sqlite`.

## Launch The App

Run the API in one terminal:

```bash
make dev
```

Run the dashboard in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`.

## Daily Workflow

```bash
make refresh
```

Then review Data Status, Alerts, Buy Board, Tracked Players and My Squad in the dashboard.

## Commands

```bash
make setup      # create a local venv and install Python deps
make init-db    # create SQLite schema
make ingest     # ingest 2025/26 historical players, gameweeks and Price Par prior
make ingest-current # ingest current official FPL bootstrap and fixtures
make ingest-underlying CSV=path/to/player_underlying.csv # optional xG/xA import
make ingest-team-underlying CSV=path/to/team_underlying.csv # optional team xG/xGA import
make price-par  # print stored Price Par curves
make backtest   # run walk-forward Buy Board vs naive PPG metrics
make snapshot-tracked # store immutable snapshots for tracked players
make generate-alerts # create dashboard alerts from tracked snapshots
make refresh    # ingest live FPL data, snapshot tracked players and generate alerts
make test       # run stdlib unit tests
make dev        # run FastAPI after setup
```

## Data Sources

- Historical data: `vaastav/Fantasy-Premier-League` raw CSV files.
- Current data: official FPL API provider stub at `https://fantasy.premierleague.com/api/bootstrap-static/`.

The ingestion layer uses provider classes so future xG/xA/team-strength sources can be added without rewriting the modelling layer.

Optional player-underlying CSV columns: `player_id`, `gameweek`, `minutes`, `xg`, `xa`, plus optional `shots`, `shots_in_box`, `big_chances`, `cbit`, `cbirt`.

Optional team-underlying CSV columns: `team_id`, `gameweek`, `xg`, `xga`, plus optional `is_home`.

## Boards

- Buy Board: ranked by Next 6 Buy Delta.
- Opportunity Score: Buy Delta adjusted by minutes and projection confidence.
- Breakout Board: forward xPPG above Value Par while actual PPG still lags.
- Trap Board: actual PPG above Value Par while forward expectation falls below par.
- Tracked Players: saved players plus current valuation and immutable snapshots.
- My Squad: owned players, selling price, hold delta, best replacement, next-3/next-6 transfer gain and hit-adjusted gain.
- Player Detail: current valuation, projection breakdown, recent gameweeks and tracked snapshots.
- Price Movements: latest stored price changes from official ingest snapshots.
- Alerts: generated events from tracked-player snapshot changes.
- Minutes Overrides: manual expected-minutes adjustments with history.
- Data Status: row counts and latest fetch timestamps for the core datasets.
