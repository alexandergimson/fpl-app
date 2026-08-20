# Modeling Notes

## Assumptions In V1

- 2025/26 is the historical prior because it includes defensive contribution scoring.
- Historical Price Par currently uses season-end price from `players_raw.csv`; price-history curves can replace this once gameweek price snapshots are ingested.
- Sample sizes at premium prices are often thin, so curve points with low support are labelled `LOW`.
- The first backtest command is a scaffold until merged gameweek ingestion is added.

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

If current-season samples are missing or too thin for a position/price, the historical prior remains the fallback.

## Opportunity Score

Opportunity Score is a visible ranking aid:

```text
Buy Delta 6 * minutes confidence * projection confidence
```

It does not replace Buy Delta; it downweights attractive deltas when minutes or projection confidence is weak.

## Projection V1

The first Buy Board uses a deliberately plain projection:

- actual PPG supplies current production
- minutes confidence shrinks that production toward the position/price Market Mean
- official fixtures supply Next 3 and Next 6 horizons
- FPL fixture difficulty applies a small temporary multiplier until rolling xG/xGA team strength lands

This is not pretending to be a finished predictive model; it gives the API/UI a working valuation path and keeps weak-minute samples from dominating the board.

Player detail includes a v1 projection breakdown. It decomposes the current `next_6_xppg` into appearance, attacking, clean-sheet, bonus/other and fixture adjustment using fields already in the board row. This is explainability scaffolding, not a substitute for xG/xA/DefCon ingestion.

## Underlying Player Data

Optional CSV ingestion stores player gameweek xG/xA rows in `player_underlying_gameweeks`.

When available, Buy Board neutral xPPG uses xG/90 and xA/90 to inform attacking expectation. When unavailable, it falls back to the existing minutes-shrunk actual PPG estimate.

## Team Strength

Optional team xG/xGA CSV ingestion stores rows in `team_underlying_gameweeks`.

When available, fixture adjustment uses opponent defensive weakness from team xGA relative to league average. When unavailable, it falls back to the small FPL fixture-difficulty multiplier.

## Provenance

Imported rows store:

- `source`
- `fetched_at`
- `data_period`

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

The first baseline is naive PPG: rank by points per game available at the forecast deadline.
