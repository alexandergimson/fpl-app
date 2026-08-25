# Current Model Audit

## Architecture

- `backend/services/boards.py` is the valuation centre. It returns one board row per FPL player using official FPL IDs.
- `backend/services/squad.py` decorates board rows for owned players and keeps squad diagnostics separate from replacement recommendations.
- `frontend/src/App.tsx` is a single workflow UI: Squad, Players, Data / Model, with Player Detail shown inline after selection.
- `backend/jobs/refresh.py` orchestrates live FPL ingest, fixture ingest, price snapshots, public squad import, tracked snapshots and alerts.

## Data Providers

- Official FPL API is the canonical current player, team, fixture, price and player-ID provider.
- Historical CSV data from `vaastav/Fantasy-Premier-League` supplies historical player/gameweek data and the Price Par prior.
- Optional local CSV imports can enrich player xG/xA/DefCon fields and team xG/xGA.

## Current Formulas

- Value Par is the position/price P75 historical slot-yield benchmark.
- Actual PPG is total FPL points divided by completed fixtures for that player's team.
- Return Delta is Value Balance divided by completed team fixtures.
- Performance Delta is process-only Underlying xPPG minus current Value Par; actual FPL points do not feed it.
- Forward Delta is Next-6 projected xPPG minus current Value Par.

## Schema Notes

- `frozen_player_gameweek_par` stores immutable historical Par rows by player, Gameweek and fixture.
- `player_cumulative_observations` stores FPL bootstrap cumulative totals so current-season xG/xA can be differenced safely.
- `game_underlying_xpts` stores derived provider-neutral process components from raw underlying rows.
- `tracked_snapshots` stores Return Delta, Performance Delta, Forward Delta compatibility value, Value Balance, projections and provenance fields.
- Most tables already carry `source`, `fetched_at` and `data_period`; richer model-run IDs remain future work.

## Known Limitations

- Frozen Pars are populated from completed team fixtures, so DNPs are included even when no `player_gameweeks` row exists.
- If frozen Pars are missing for a player/team fixture set, realised Value Balance and Return Delta stay null instead of falling back to today's Value Par.
- Underlying xPPG is still the v1 deterministic blend, not the later empirical-Bayes player ability model.
- Clean-sheet, bonus and save process EVs are zero in `game_underlying_xpts` until a provider supplies expected process inputs.
- Team strength is a rolling/fallback baseline, not the state-space challenger.
