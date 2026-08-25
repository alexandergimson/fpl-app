# Model Roadmap

## Completed Foundations

- Official FPL player ID is the canonical player identity.
- Current player, team, fixture, price, ownership and status data come from the official FPL API.
- Price Par uses position-specific, price-specific P75 historical slot yield with monotonic smoothing and interpolation.
- Core board rows expose Value Par, Frozen GW Par-derived Value Balance, Return Delta, Underlying xPPG, Performance Delta, Next-6 xPPG and Forward Delta.
- Raw underlying rows now produce provider-neutral `game_underlying_xpts` rows with appearance, xG goal, xA assist and DefCon components.
- FPL bootstrap cumulative xG/xA is differenced into Gameweek observations before being used by Performance Delta.
- Squad and Players tables use the simplified Return / Performance / Forward Delta workflow.
- Frozen Par is canonical at one row per player per FPL Gameweek, including Double Gameweeks.
- Walk-forward backtests evaluate future excess points versus future frozen GW Pars and report frozen-Par coverage.
- Tracked snapshots store model version plus component-version metadata for Par, data, minutes, role, team strength, underlying and projection logic.
- Underlying attacking and DefCon rates are shrunk toward position averages with a deterministic 900-minute prior; bonus and save rates use the same baseline pattern.
- Team strength uses rolling team xG/xGA shrunk toward league average, with FPL fixture difficulty as the no-data fallback.
- Minutes use a hurdle profile: start probability, conditional starter minutes, substitute probability, substitute minutes and P(60+).

## Next Phases

1. Add formal model-run IDs when multiple trained/challenger models exist.

## Promotion Rule

Every challenger model stays experimental until walk-forward backtests show an out-of-sample improvement or materially better calibration/explainability at equivalent accuracy.
