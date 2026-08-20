# Implementation Plan

## Phase 1: Data Model And FPL Ingestion

- SQLite is the local source of truth.
- `players` stores FPL player identity, price, points, minutes, status and provenance.
- provider classes isolate the official FPL API and historical `vaastav/Fantasy-Premier-League` files.
- `price_history`, `tracked_snapshots`, `squad_players`, `minutes_overrides` and `alerts` are present now because later screens need stable tables, not because v1 fills every one.

## Phase 2: Historical Price Par

- Use 2025/26 `players_raw.csv` as the first prior.
- Filter to configurable reliable players, default `2000` minutes.
- Use `points_per_team_gameweek = total_points / 38` as the benchmark metric.
- Group by position and exact price, calculate Market Mean and weighted 75th percentile Value Par.
- Apply monotonic smoothing with a small in-repo PAVA implementation.
- Interpolate between stored points at valuation time.

## Phase 3: Dynamic Current-Price Par

- Evaluate every current player against current price, not starting price. Implemented through Buy Board interpolation.
- Blend historical and current-season curves with configured GW weights.
- Keep confidence low when evaluating outside observed historical price ranges.

## Phase 4: Projection Engine

- Start with transparent fixture components: appearance, goals, assists, clean sheets, DefCon, bonus, saves and cards.
- Minutes are a veto through expected minutes and manual override history.
- Keep each component inspectable on player detail.
- V1 uses minutes-shrunk actual PPG until fixture and event ingestion are available.

## Phase 5: Team Strength And Fixtures

- Official fixture ingestion is implemented.
- V1 uses FPL fixture difficulty as a small fallback multiplier.
- Use rolling team xG/xGA, split home/away where available.
- Regress early-season values toward prior strength.
- Keep FPL fixture difficulty as context, not the primary model input.

## Phase 6: Backtesting

- Walk-forward windows only use data available before the prediction deadline.
- Compare naive PPG, neutral model, fixture-adjusted model and later versions.
- Track MAE, RMSE, Spearman, top-quartile hit rate and Buy Board precision.

## Phase 7-10: API, Dashboard, Tracking, Squad

- FastAPI exposes players, Price Par, boards, tracked players and squad analysis.
- React dashboard prioritises sortable tables, deltas, sparklines and search.
- Breakout and Trap board API/UI slices are implemented from the same valuation rows as Buy Board; Breakout uses forward expectation until true xG/xA underlying data exists.
- Tracked player API/UI slice is implemented with immutable per-gameweek snapshots.
- My Squad API/UI slice is implemented with selling price, hold delta and best affordable replacement.
- My Squad UI can add/remove players, enter purchase price and adjust bank for replacement budgets.
- Official current ingest stores price snapshots and the dashboard exposes recent price movements.
- Player detail API/UI slice is implemented with valuation, recent gameweeks and tracked snapshots.
- Player detail shows recent gameweek and tracked-snapshot trend charts.
- Dashboard alert generation is implemented for tracked-player snapshot changes.
- Minutes override API is implemented and applied to board projections.
- Tracked snapshots are immutable by gameweek.
- Squad analysis separates Buy Value from Hold Value using FPL selling-price rules.

## Phase 11: Polish And Documentation

- Add focused tests for each modelling rule as it lands.
- Keep assumptions documented in `docs/modeling.md`.
