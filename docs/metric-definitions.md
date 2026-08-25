# Metric Definitions

## Value Par

Expected FPL points per team Gameweek for a good player at the same position and price.

## Frozen GW Par

The Value Par recorded for a player at the price and position that applied in a completed Gameweek. Frozen Pars are immutable and stored in `frozen_player_gameweek_par`.

## Value Balance

```text
actual FPL points - sum(frozen GW Pars)
```

Positive means the player has banked points above the price/position hurdle. Negative means they have cost points versus the hurdle.

## Return Delta

```text
Value Balance / completed team fixtures
```

This is the realised outcome metric. If the player's team has not completed a fixture, Return Delta is null. If the team played and the player did not, their actual points are zero.

## Underlying xPPG

Fixture-neutral expected FPL points per Gameweek from the current process model.

## Performance Delta

```text
Underlying xPPG - current Value Par
```

This is the process metric.

## Next-6 xPPG

Projected average points per FPL Gameweek over the next six Gameweeks.

## Forward Delta

```text
Next-6 xPPG - current Value Par
```

This is the primary market ranking metric and is labelled `Best Value` in the Players table.
