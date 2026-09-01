# OpenFPL Scout AI research

Audited against [`elcaiseri/OpenFPL-Scout-AI`](https://github.com/elcaiseri/OpenFPL-Scout-AI) commit `b771cfae2ee7dc92d4372b715d3e516a579bbe35` on 1 September 2026. This note documents an evaluation only; the production Performance PPG and Next 6 models are unchanged.

## Useful approach

OpenFPL normalises old and new column names into one feature contract, then averages each player's five matches before the forecast Gameweek. Training features are shifted by one match. Both fixtures in a double Gameweek receive the history available at the start of that Gameweek, preventing fixture one from leaking into fixture two.

Its deployment ensemble is a weighted average of Ridge/linear regression, XGBoost, CatBoost and MLP pipelines. At least three models must succeed and final predictions are clipped at zero. The repository says training uses five-fold chronological cross-validation plus an untouched latest-season holdout. The referenced trainer is not present at the audited commit, so the full training and weight-selection implementation cannot be independently verified from the repository.

Features cover identity, position, team/opponent, venue, Gameweek, price, ownership, minutes, shooting/xG, creation/xA, team defensive outcomes, defensive actions, expected points and touches/carries. Missing fields stay null for model-pipeline imputation rather than being replaced with invented football metrics.

## FPL Data enrichment audit

The source is the public CSV download on [FPL Data Statistics](https://www.fpl-data.co.uk/statistics). Its season selector currently includes `2026_27`. A non-persisted audit found 1,236 rows through GW2 and all 626 external player IDs matched current Official FPL IDs (the official bootstrap had three additional players). The current CSV header supplies Official FPL IDs and fixture context plus:

- shots, shots on target, shots in box, xG, non-penalty xG, goals and non-penalty goals;
- chances created, xA and assists;
- xGC, goals conceded, expected clean sheet and clean sheet;
- combined clearances/blocks/interceptions, recoveries, tackles and defensive contribution;
- xGI, non-penalty xGI, expected points, actual points and PvsxP;
- touches and opposition-box touches.

It does not currently supply separate clearances, shot blocks or interceptions, final-third carries, penalty-area carries, crosses, offsides, big chances, post-shot xG or goals prevented.

OpenFPL joins enrichment to official history on FPL player ID, Gameweek, opponent and home/away; requires at least an 80% match ratio; rejects stale Gameweek coverage and duplicate keys; and fills null official fields only. These are good integration rules.

The OpenFPL code is MIT licensed, but that licence does not grant rights to the third-party FPL Data CSV. OpenFPL explicitly records FPL Data reuse permission as requested/pending, requires acknowledgement, discourages redistribution and provides a kill switch. Therefore FPL Data is not approved as a production dependency here. If the data owner grants suitable permission, implement a disabled-by-default provider with exact-season validation, fixture-level ID matching, an 80% minimum match ratio, null-only filling, provenance and refresh health diagnostics.

## Challenger recommendation

Build the challenger offline first. At each historical deadline, create prior-five-match features with a Gameweek-level cutoff, give every DGW fixture the same pre-deadline history, train only on earlier seasons/folds, and store each component prediction plus the ensemble prediction. Compare the current Next 6 model and challenger against fixture and six-Gameweek actual points using MAE, RMSE, calibration by predicted band, rank correlation and captain/top-N hit rates. Promote nothing until it beats the current model across an untouched holdout and live forward test.
