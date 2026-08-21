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

Then review My Squad, All Players, Tracked Players and Data / Model in the dashboard.

## Commands

```bash
make setup      # create a local venv and install Python deps
make init-db    # create SQLite schema
make ingest     # ingest 2025/26 historical players, gameweeks and Price Par prior
make ingest-current # ingest current official FPL bootstrap and fixtures
make ingest-underlying CSV=path/to/player_underlying.csv # optional xG/xA import
make ingest-team-underlying CSV=path/to/team_underlying.csv # optional team xG/xGA import
make price-par  # print stored Price Par curves
make backtest   # run walk-forward valuation vs naive PPG metrics
make snapshot-tracked # store immutable snapshots for tracked players
make generate-alerts # create dashboard alerts from tracked snapshots
make refresh    # ingest live FPL data, snapshot tracked players and generate alerts
make test       # run stdlib unit tests
make dev        # run FastAPI after setup
```

## Data Sources

- Historical data: `vaastav/Fantasy-Premier-League` raw CSV files.
- Current player data: official FPL API at `https://fantasy.premierleague.com/api/bootstrap-static/`.

The official FPL `elements.id` is the canonical player ID throughout the app. Current ingest also stores FPL bootstrap xG/xA aggregates as player-underlying rows once GW1+ data exists.

Optional player-underlying CSV columns: `player_id`, `gameweek`, `minutes`, `xg`, `xa`, plus optional `shots`, `shots_in_box`, `big_chances`, `cbit`, `cbirt`.

Optional team-underlying CSV columns: `team_id`, `gameweek`, `xg`, `xga`, plus optional `is_home`.

## Core Tables

- My Squad: squad health using Historical Delta, Forward Delta, confidence, minutes and value trend.
- All Players: full market table sorted by Forward Delta by default, with position, price, team, ownership, confidence and tracked filters.
- Emerging: All Players quick filter for negative Historical Delta and positive Forward Delta.
- Regression Risk: All Players quick filter for positive Historical Delta and negative Forward Delta.
- Tracked Players: saved players plus current valuation and immutable snapshots.
- Player Detail: current valuation, projection breakdown, recent gameweeks and tracked snapshots.
- Price Movements: latest stored price changes from official ingest snapshots.
- Alerts: generated events from tracked-player snapshot changes.
- Minutes Overrides: manual expected-minutes adjustments with history.
- Data Status: row counts and latest fetch timestamps for the core datasets.

My Squad can import the latest public 15-player squad from an FPL Team ID. Public import reflects the latest available Gameweek picks, not unsubmitted/private transfer drafts.
