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

- Evaluate every current player against current price, not starting price. Implemented through All Players interpolation.
- Blend historical and current-season curves with configured GW weights.
- Data Health exposes the active historical-prior/current-season blend.
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
- Track MAE, RMSE, Spearman, top-quartile hit rate and market-table precision.

## Phase 7-10: API, Dashboard, Tracking, Squad

- FastAPI exposes players, Price Par, All Players, tracked players and squad analysis.
- React dashboard prioritises sortable tables, deltas, sparklines and search.
- Emerging and Regression Risk are quick filters on the same All Players valuation rows.
- Tracked player API/UI slice is implemented with immutable per-gameweek snapshots.
- Tracked snapshots preserve model version, data cutoff, expected minutes, confidence and projection inputs.
- My Squad API/UI slice is implemented with selling price, Return Delta, Performance Delta and Forward Delta.
- My Squad UI can add/remove players, enter purchase price and adjust bank for replacement budgets.
- My Squad shows next-3, next-6, expected minutes, confidence and value trend.
- Official current ingest stores price snapshots and the dashboard exposes recent price movements.
- Dashboard workflow is centered on My Squad, All Players, Tracked Players and Data / Model.
- Dashboard data status shows source row counts, current gameweek and latest fetch timestamps.
- Current FPL ingest records ingestion runs and data-health events for live pipeline visibility.
- Current FPL ingest is the canonical player provider and stores GW1+ FPL xG/xA aggregates against FPL player IDs.
- `make refresh` runs the local live workflow: current ingest, tracked snapshots and alert generation.
- Data Health shows feed timestamps, expected/received counts, latest runs and warning events.
- Alerts can be generated and acknowledged from the dashboard.
- All Players filters include position, team, price range, ownership, expected minutes, confidence and tracked-only.
- Player detail API/UI slice is implemented with valuation, recent gameweeks and tracked snapshots.
- Player detail shows recent gameweek and tracked-snapshot trend charts.
- Player detail can save minutes overrides and shows the latest override note.
- Dashboard alert generation is implemented for tracked-player snapshot changes.
- Minutes override API is implemented and applied to board projections.
- Tracked snapshots are immutable by gameweek.
- Squad analysis separates Buy Value from Hold Value using FPL selling-price rules.

## Phase 11: Polish And Documentation

- Focused tests cover the modelling and service rules added for v1.
- `README.md` documents setup, launch commands and daily workflow.
- `docs/modeling.md` documents v1 assumptions, projections, tracking, squad valuation, alerts and provenance.

## Optional Post-V1

- Replace optional CSV xG/xA imports with an automated provider when a reliable source is chosen.
- Add Understat as the first automated team-strength enrichment provider.
- Add deployment packaging if the app needs to run somewhere other than local dev.
