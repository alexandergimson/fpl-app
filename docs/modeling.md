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

## Projection V1

The first Buy Board uses a deliberately plain projection:

- actual PPG supplies current production
- minutes confidence shrinks that production toward the position/price Market Mean
- official fixtures supply Next 3 and Next 6 horizons
- FPL fixture difficulty applies a small temporary multiplier until rolling xG/xGA team strength lands

This is not pretending to be a finished predictive model; it gives the API/UI a working valuation path and keeps weak-minute samples from dominating the board.

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
