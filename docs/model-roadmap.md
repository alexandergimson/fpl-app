# Model Roadmap

## Completed Foundations

- Official FPL player ID is the canonical player identity.
- Current player, team, fixture, price, ownership and status data come from the official FPL API.
- Price Par uses position-specific, price-specific P75 historical slot yield with monotonic smoothing and interpolation.
- Core board rows expose Value Par, Frozen GW Par-derived Value Balance, Return Delta, Underlying xPPG, Performance Delta, Next-6 xPPG and Forward Delta.
- Squad and Players tables use the simplified Return / Performance / Forward Delta workflow.

## Next Phases

1. Add a provider-neutral underlying-match schema before wiring Understat.
2. Build the deterministic regressed player-ability baseline for xG, xA, DefCon, bonus and saves.
3. Upgrade team strength to rolling xG/xGA with shrinkage and explicit model versions.
4. Replace heuristic minutes with start probability, conditional starter minutes, sub probability, sub minutes and P(60+).
5. Expand immutable snapshots with model-run IDs and component versions.
6. Harden walk-forward backtests around future excess points versus frozen future Pars.

## Promotion Rule

Every challenger model stays experimental until walk-forward backtests show an out-of-sample improvement or materially better calibration/explainability at equivalent accuracy.
