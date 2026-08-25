# Modeling Notes

## Assumptions In V1

- 2025/26 is the historical prior because it includes defensive contribution scoring.
- Historical Price Par currently uses season-end price from `players_raw.csv`; current-season price snapshots are stored separately for movement tracking.
- Sample sizes at premium prices are often thin, so curve points with low support are labelled `LOW`.
- Backtests use imported gameweek rows and only look at data available through the simulated deadline.

## Price Par

Market Mean is the mean viable-player production for a position and price.

Value Par is the 75th percentile viable-player production for a position and price.

The primary benchmark metric is:

```text
points_per_team_gameweek = total_points / 38
```

`points_per_90` remains a diagnostic, but does not drive squad valuation.

## Dynamic Price Par

Historical Price Par remains the prior.

When a board is evaluated with `as_of_gw`, the app builds a current-season curve from player gameweek data available through that GW, annualises the sample, and blends it with the historical prior using the configured gameweek weights.

Current-season weight ramps by gameweek:

```text
GW0:    100% prior / 0% current
GW1-3:   75% prior / 25% current
GW4-6:   60% prior / 40% current
GW7-10:  40% prior / 60% current
GW11-15: 25% prior / 75% current
GW16+:   15% prior / 85% current
```

If current-season samples are missing or too thin for a position/price, the historical prior remains the fallback.

## Canonical Value Metrics

Value Par is the hurdle rate for a good FPL player at the same position and current price.

Frozen GW Par is the Value Par that applied to a player for an already-completed Gameweek. It is stored immutably in `frozen_player_gameweek_par` when gameweek rows exist.

Value Balance is:

```text
actual FPL points - sum(frozen GW Pars)
```

If frozen Pars are not available yet, the board falls back to today's Value Par multiplied by team completed fixtures. That fallback keeps the live app usable, but frozen Pars are the authoritative source once populated.

Return Delta is:

```text
Value Balance / completed team fixtures
```

If the team has not completed a league fixture yet, Actual PPG, Value Balance and Return Delta are null and the UI displays `-`. If the team has played and the player did not appear, actual points are zero and Return Delta is negative against Par.

Performance Delta is:

```text
Underlying xPPG - current Value Par
```

Forward Delta is:

```text
Next-6 xPPG - Value Par
```

Players sorts by Forward Delta by default using the label Best Value. Emerging and Regression Risk are quick filters over the same player universe, not separate model outputs.

The main UI uses progressive disclosure: Squad shows Player, Position, Price, Return Delta, Performance Delta and Forward Delta. Players shows Player, Team, Position, Price, Performance Delta, Forward Delta and Track. Market Mean, Actual PPG, Value Par, Underlying xPPG, expected minutes, start probability, ownership and projection components stay in Player Detail or Data / Model.

## Projection V1

The first market table uses a deliberately plain projection:

- Actual PPG supplies realised current-season production once the player's team has completed fixtures
- minutes confidence shrinks that production toward the position/price Market Mean
- official fixtures supply Next 3 and Next 6 horizons
- FPL fixture difficulty applies a small temporary multiplier until rolling xG/xGA team strength lands

This is not pretending to be a finished predictive model; it gives the API/UI a working valuation path and keeps weak-minute samples from dominating the board.

Player detail includes a v1 projection breakdown. It decomposes the current `next_6_xppg` into appearance, attacking, clean-sheet, bonus/other and fixture adjustment using fields already in the board row. This is explainability scaffolding, not a substitute for xG/xA/DefCon ingestion.

Manual minutes overrides set start probability, expected starter minutes, substitute probability and substitute minutes. Boards use the latest override for projection minutes and player detail keeps the override history visible.

## Underlying Player Data

The official FPL API is the canonical player provider and ID system. Current ingest stores FPL bootstrap xG/xA aggregates in `player_underlying_gameweeks` for GW1+ using `elements.id` as `player_id`.

Optional CSV ingestion can still store player gameweek xG/xA rows in `player_underlying_gameweeks` for validation or manual enrichment.

When available, neutral xPPG uses xG/90 and xA/90 to inform attacking expectation. When unavailable, it falls back to the existing minutes-shrunk actual PPG estimate.

## Team Strength

Optional team xG/xGA CSV ingestion stores rows in `team_underlying_gameweeks`.

When available, fixture adjustment uses opponent defensive weakness from team xGA relative to league average. When unavailable, it falls back to the small FPL fixture-difficulty multiplier.

Understat is the intended first automated team-strength enrichment provider, but it is not wired until team xG/xGA ingestion is added.

## Clean Sheets

GK, DEF and MID projections now estimate clean-sheet EV separately from attacking fixture adjustment.

Upcoming expected opponent goals come from opponent attack strength, own defensive weakness and a 1.35 league-average goals prior. When team xG/xGA is unavailable, FPL fixture difficulty supplies a small fallback. Clean-sheet probability uses:

```text
P(clean sheet) = exp(-expected opponent goals)
```

The model then applies FPL clean-sheet points by position and expected 60-minute probability.

## Defensive Contributions

Optional player-underlying CSV ingestion supports `cbit` and `cbirt`.

DEF projections use `cbit` against the 10-action threshold. MID/FWD projections use `cbirt` against the 12-action threshold. The v1 probability is a capped rate-to-threshold estimate from per-90 actions, multiplied by expected 60-minute probability and capped at the +2 FPL points available per match.

## Bonus

Bonus EV uses `player_gameweeks.bonus` as a conservative bonus/90 rate regressed toward the player's positional average with a 900-minute prior. It appears as a separate projection component and is included in component-based projections when player underlying data is available.

## Goalkeepers

Goalkeeper save EV uses `player_gameweeks.saves`, regressed toward the goalkeeper average with a 900-minute prior. Projected saves convert to FPL save points at one point per three saves and appear as a separate player-detail component.

## Captaincy

Board rows expose `forward_delta` as the canonical market ranking metric. Legacy `buy_delta_6` remains as a compatibility alias. The captain adjustment is deliberately simple and separate: players priced at £10.0m+ get a partial captaincy multiplier, and players priced at £12.0m+ get a larger one. It does not replace the primary ranking.

## Role Overrides

Manual role overrides can mark penalties, direct free kicks, corners and indirect free kicks. The latest role override adds a conservative role xPPG boost and is shown in player detail.

## Projection Confidence

Projection confidence combines minutes security, available underlying-data sample, role stability and FPL availability status. It still deliberately stays simple; injury/detail uncertainty can replace the coarse status factor when richer data is available.

## Tracking Momentum

Tracked-player momentum is `latest snapshot buy_delta - previous snapshot buy_delta`, where `buy_delta` stores the Forward Delta compatibility value. Snapshots also store Return Delta, Performance Delta and Value Balance.

Alerts are generated from tracked snapshots and deduped by season, player, gameweek and alert kind. Current v1 alerts focus on large buy-delta movement and price movement.

## Squad Diagnostics

My Squad stores purchase price, current price and FPL selling price. The table diagnoses owned players with Return Delta, Performance Delta and Forward Delta. It deliberately does not choose replacements.

## Price Movements

Official current ingest snapshots player prices into `price_history`. The dashboard reports latest price changes from those snapshots.

## Provenance

Imported rows store:

- `source`
- `fetched_at`
- `data_period`

Data Status summarizes row counts, current gameweek and latest fetch timestamps for the core datasets so stale or missing inputs are visible before judging recommendations.

## Gameweek History

Historical `merged_gw.csv` rows are stored in `player_gameweeks`.

Backtest-style board generation can pass `as_of_gw`, which aggregates only rows at or before that gameweek. This prevents using end-of-season totals when ranking a historical deadline.

## Backtesting V1

`make backtest` evaluates walk-forward Buy Board snapshots:

- train through GW5, predict GW6-10
- train through GW10, predict GW11-16
- train through GW15, predict GW16-21
- train through GW20, predict GW21-26

For top 10 and top 20 ranked players it reports MAE, RMSE, Spearman rank correlation, average excess points over Value Par, the share beating Value Par and the share landing in the future top quartile.

The first baseline is naive PPG: rank by points per game available at the forecast deadline. The command also compares Buy Delta, Opportunity Score and Captain-adjusted ranking over the same walk-forward windows.
