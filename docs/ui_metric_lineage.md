# UI metric lineage

Selective canonical metrics added in this pass.

| UI location | Metric | Endpoint | Backend field | Materialized source | Upstream source |
| --- | --- | --- | --- | --- | --- |
| My Squad summary | Squad Value | `GET /squad` | `current_price` | `current_player_metrics.current_price` | FPL bootstrap `elements.now_cost` via `players.current_price` |
| My Squad summary | Sell Value | `GET /squad` | `selling_price` | `squad_players.selling_price` joined to `current_player_metrics` | Local squad state derived from FPL current price and saved purchase price |
| My Squad summary | Locked Gain | `GET /squad` | `selling_price - purchase_price` | `squad_players.selling_price`, `squad_players.purchase_price` | Local squad state; public imports use current FPL price as purchase price |
| Player detail metrics | Opp xGA6 | `GET /players/{player_id}` | `current.expected_opponent_goals_6` | `current_prediction_snapshots.prediction_json.expected_opponent_goals_6` | Fixture projection from `fixtures` plus Understat-enriched `team_underlying_gameweeks` where available |
| Player detail metrics | Fixture | `GET /players/{player_id}` | `current.fixture_factor_6` | `current_prediction_snapshots.prediction_json.fixture_factor_6` | `fixtures.team_h_difficulty`, `fixtures.team_a_difficulty`, and team-strength adjustment |
| Player detail metrics | Captain Delta | `GET /players/{player_id}` | `current.captain_adjusted_delta` | `current_prediction_snapshots.prediction_json.captain_adjusted_delta` | Materialized valuation row from FPL canonical player data and Par curve |
| Player detail metrics | Opportunity | `GET /players/{player_id}` | `current.opportunity_score` | `current_prediction_snapshots.prediction_json.opportunity_score` | Materialized valuation row from forward delta, expected minutes, and projection confidence |
| Player detail fixtures | Opponent label | `GET /players/{player_id}` | `current.fixture_projection[].fixtures[].opponent` | `current_prediction_snapshots.prediction_json.fixture_projection` | `teams.short_name` joined from canonical FPL team IDs |

Skipped: raw Understat shot metrics and full manager chip/bank context are not in the existing UI materialized read model, so they remain backend-only until the refresh model deliberately exposes them.
