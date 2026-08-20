import unittest

from backend.models.price_par import ParPoint, interpolate, pava
from backend.models.projections import clean_sheet_ev, defcon_ev, expected_minutes, role_xppg
from backend.models.projections import projection_breakdown
import pandas as pd
from backend.services.valuation import captain_adjusted_delta, captaincy_weight, player_status, projection_confidence, selling_price
from backend.services.boards import breakout_board, buy_board, infer_gameweeks, trap_board
from backend.services.bonus import bonus_rates, bonus_xppg
from backend.services.goalkeepers import save_rates, save_xppg
from backend.data.db import connect
from backend.services.fixtures import adjusted_horizon_ppg, clean_sheet_horizon_ev, upcoming_expected_opponent_goals, upcoming_fixture_factors
from backend.services.history import future_points, player_totals_as_of
from backend.backtests.metrics import evaluate_model, evaluate_rows, mae, ranks, rmse, spearman
from backend.services.tracking import snapshot_tracked, track_player, tracked_momentum, tracked_players, tracked_snapshots, tracking_status, untrack_player
from backend.services.squad import remove_squad_player, squad_analysis, squad_verdict, upsert_squad_player
from backend.services.player_detail import player_detail, recent_gameweeks
from backend.services.alerts import acknowledge_alert, generate_tracked_alerts, list_alerts
from backend.services.minutes import add_minutes_override, latest_minutes_overrides
from backend.services.roles import add_role_override, latest_role_overrides, role_history
from backend.ingestion.loaders import replace_player_underlying
from backend.ingestion.loaders import replace_team_underlying, snapshot_prices
from backend.services.prices import price_movements
from backend.services.underlying import attacking_xppg, defcon_xppg, player_underlying_rates
from backend.services.team_strength import team_strengths
from backend.services.price_par import blended_par_for, current_curve_points


class ModelTests(unittest.TestCase):
    def test_pava_makes_curve_monotonic(self):
        self.assertEqual(pava([3, 2, 4], [1, 1, 1]), [2.5, 2.5, 4])

    def test_interpolate_current_price(self):
        points = [
            ParPoint("MID", 6.5, 4.0, 4.2, 5, "MEDIUM"),
            ParPoint("MID", 7.0, 4.2, 4.6, 5, "MEDIUM"),
        ]
        self.assertEqual(interpolate(points, "MID", 6.75), (4.1, 4.4, "MEDIUM"))

    def test_selling_price(self):
        self.assertEqual(selling_price(5.0, 5.3), 5.1)
        self.assertEqual(selling_price(5.0, 4.8), 4.8)

    def test_captain_adjusted_delta_for_premium_players(self):
        self.assertEqual(captaincy_weight(9.5), 0.0)
        self.assertEqual(captaincy_weight(10.0), 0.35)
        self.assertAlmostEqual(captain_adjusted_delta(6.0, 5.0, 12.0), 4.6)

    def test_projection_confidence_combines_sample_and_availability(self):
        high = projection_confidence(1.0, 900, "a", True)
        low = projection_confidence(0.2, 0, "i", False)
        self.assertGreater(high, low)
        self.assertLessEqual(high, 1.0)

    def test_expected_minutes(self):
        self.assertAlmostEqual(expected_minutes(0.8, 75, 0.15, 20), 63)

    def test_role_xppg(self):
        role = {"penalties": 1, "direct_free_kicks": 0, "corners": 1, "indirect_free_kicks": 0}
        self.assertAlmostEqual(role_xppg("MID", 90, role), 0.84)

    def test_clean_sheet_poisson(self):
        self.assertAlmostEqual(clean_sheet_ev(1.0, 4, 1.0), 1.4715, places=3)
        self.assertAlmostEqual(clean_sheet_horizon_ev([1.0], "DEF", 90, 1), 1.4715, places=3)

    def test_defcon_cap(self):
        self.assertEqual(defcon_ev(2), 2)
        self.assertEqual(defcon_xppg("DEF", 90, 10, 0), 2)
        self.assertEqual(defcon_xppg("MID", 30, 0, 12), 1)

    def test_bonus_xppg_scales_by_minutes(self):
        self.assertEqual(bonus_xppg(45, 1.0), 0.5)

    def test_save_xppg_only_applies_to_goalkeepers(self):
        self.assertEqual(save_xppg("GK", 90, 3), 1)
        self.assertEqual(save_xppg("DEF", 90, 3), 0)

    def test_status(self):
        self.assertEqual(player_status(0.8, 0.4, 0.9), "STRONG BUY")
        self.assertEqual(player_status(-0.6, -0.2, 0.8), "SELL")

    def test_buy_board_uses_current_price(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "MID", 5.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "MID", 6.0, 4.0, 4.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES (
                  '2026-27', 1, NULL, 'Test', '', '', NULL, 'TST', 'MID',
                  5.5, 40, 900, 10.0, 'a', 'test', 'now', 'test'
                )
                """
            )
            row = buy_board(con, "2026-27", "2026-27", 10, 1)[0]
        self.assertEqual(row["value_par"], 4.0)
        self.assertIn("opportunity_score", row)
        self.assertIn("captain_adjusted_delta", row)

    def test_price_snapshots_report_movements(self):
        with connect(":memory:") as con:
            con.execute(
                """
                INSERT INTO players VALUES (
                  '2026-27', 1, NULL, 'Mover', '', '', 1, 'TST', 'MID',
                  5.1, 10, 90, 10.0, 'a', 'test', 'now', 'test'
                )
                """
            )
            first = pd.DataFrame([{"id": 1, "now_cost": 50}])
            latest = pd.DataFrame([{"id": 1, "now_cost": 51}])
            first.attrs["current_gameweek"] = 1
            latest.attrs["current_gameweek"] = 2
            snapshot_prices(con, "2026-27", first, "test", "2026-08-01T00:00:00")
            snapshot_prices(con, "2026-27", latest, "test", "2026-08-08T00:00:00")
            rows = price_movements(con, "2026-27")
        self.assertEqual(rows[0]["player"], "Mover")
        self.assertEqual(rows[0]["price_change"], 0.1)

    def test_preseason_bootstrap_totals_use_full_season_denominator(self):
        rows = [{"total_points": 240}]
        self.assertEqual(infer_gameweeks(rows, "2026-27", "2026-27"), 38)

    def test_fixture_factor_adjusts_projection_horizon(self):
        with connect(":memory:") as con:
            con.execute("INSERT INTO app_state VALUES ('2026-27', 'current_gameweek', '1', CURRENT_TIMESTAMP)")
            con.execute(
                """
                INSERT INTO fixtures VALUES
                ('2026-27', 1, 2, '', 1, 2, 2, 4, 0, 'test', 'now', 'test'),
                ('2026-27', 2, 3, '', 3, 1, 3, 1, 0, 'test', 'now', 'test')
                """
            )
            factors = upcoming_fixture_factors(con, "2026-27", 1, 3)
        self.assertEqual(factors, [1.08, 1.16])
        self.assertAlmostEqual(adjusted_horizon_ppg(5, factors, 3), 5.4)

    def test_buy_board_includes_fixture_adjustment(self):
        with connect(":memory:") as con:
            for price in (5.0, 6.0):
                con.execute(
                    "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("2026-27", "test", "MID", price, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
                )
            con.execute("INSERT INTO app_state VALUES ('2026-27', 'current_gameweek', '1', CURRENT_TIMESTAMP)")
            con.execute("INSERT INTO fixtures VALUES ('2026-27', 1, 2, '', 1, 2, 1, 5, 0, 'test', 'now', 'test')")
            con.execute(
                """
                INSERT INTO players VALUES (
                  '2026-27', 1, NULL, 'Test', '', '', 1, 'TST', 'MID',
                  5.0, 38, 3420, 10.0, 'a', 'test', 'now', 'test'
                )
                """
            )
            row = buy_board(con, "2026-27", "2026-27", 38, 1)[0]
        self.assertGreater(row["next_3_xppg"], row["neutral_xppg"])

    def test_buy_board_as_of_skips_players_without_history(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "MID", 5.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES
                ('2025-26', 1, NULL, 'Future', '', '', 1, 'TST', 'MID', 5.0, 200, 3000, 10.0, 'a', 'test', 'now', 'test'),
                ('2025-26', 2, NULL, 'Known', '', '', 1, 'TST', 'MID', 5.0, 20, 450, 10.0, 'a', 'test', 'now', 'test')
                """
            )
            con.execute(
                """
                INSERT INTO player_gameweeks (
                  season, player_id, gameweek, fixture_id, opponent_team, was_home,
                  total_points, minutes, starts, goals_scored, assists, clean_sheets,
                  goals_conceded, saves, bonus, bps, selected, transfers_in, transfers_out,
                  value, source, fetched_at, data_period
                ) VALUES
                ('2025-26', 2, 1, 1, 2, 1, 5, 90, 1, 0, 0, 0, 0, 0, 0, 0, NULL, NULL, NULL, 5.0, 'test', 'now', 'test')
                """
            )
            rows = buy_board(con, "2025-26", "2026-27", None, 10, as_of_gw=1)
        self.assertEqual([row["player"] for row in rows], ["Known"])

    def test_breakout_and_trap_boards_filter_buy_board_rows(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "MID", 5.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES
                ('2026-27', 1, NULL, 'Break', '', '', 1, 'TST', 'MID', 5.0, 35, 900, 10.0, 'a', 'test', 'now', 'test'),
                ('2026-27', 2, NULL, 'Trap', '', '', 1, 'TST', 'MID', 5.0, 50, 90, 10.0, 'a', 'test', 'now', 'test')
                """
            )
            con.execute("INSERT INTO fixtures VALUES ('2026-27', 1, 1, '', 1, 2, 1, 5, 0, 'test', 'now', 'test')")
            breakouts = breakout_board(con, "2026-27", "2026-27", 10, 10)
            traps = trap_board(con, "2026-27", "2026-27", 10, 10)
        self.assertEqual([row["player"] for row in breakouts], ["Break"])
        self.assertEqual([row["player"] for row in traps], ["Trap"])

    def test_history_as_of_prevents_future_leakage(self):
        with connect(":memory:") as con:
            con.execute(
                """
                INSERT INTO player_gameweeks (
                  season, player_id, gameweek, fixture_id, opponent_team, was_home,
                  total_points, minutes, starts, goals_scored, assists, clean_sheets,
                  goals_conceded, saves, bonus, bps, selected, transfers_in, transfers_out,
                  value, source, fetched_at, data_period
                ) VALUES
                ('2025-26', 1, 1, 1, 2, 1, 5, 90, 1, 0, 0, 0, 0, 0, 0, 0, NULL, NULL, NULL, 5.0, 'test', 'now', 'test'),
                ('2025-26', 1, 2, 2, 3, 0, 9, 90, 1, 0, 0, 0, 0, 0, 0, 0, NULL, NULL, NULL, 5.1, 'test', 'now', 'test')
                """
            )
            totals = player_totals_as_of(con, "2025-26", 1)
            future = future_points(con, "2025-26", 1, 2, 2)
        self.assertEqual(totals[1]["total_points"], 5)
        self.assertEqual(totals[1]["current_price"], 5.0)
        self.assertEqual(future, 9)

    def test_backtest_error_metrics(self):
        self.assertEqual(mae([2, -4]), 3)
        self.assertAlmostEqual(rmse([3, 4]), 3.5355, places=3)
        self.assertEqual(ranks([10, 20, 20]), [1, 2.5, 2.5])
        self.assertAlmostEqual(spearman([1, 2, 3], [1, 2, 3]), 1)

    def test_evaluate_rows_can_use_naive_prediction_key(self):
        with connect(":memory:") as con:
            con.execute(
                """
                INSERT INTO player_gameweeks (
                  season, player_id, gameweek, fixture_id, opponent_team, was_home,
                  total_points, minutes, starts, goals_scored, assists, clean_sheets,
                  goals_conceded, saves, bonus, bps, selected, transfers_in, transfers_out,
                  value, source, fetched_at, data_period
                ) VALUES
                ('2025-26', 1, 2, 1, 2, 1, 6, 90, 1, 0, 0, 0, 0, 0, 0, 0, NULL, NULL, NULL, 5.0, 'test', 'now', 'test')
                """
            )
            rows = [{"player_id": 1, "actual_ppg": 5, "next_6_xppg": 4, "value_par": 3}]
            result = evaluate_rows(con, "2025-26", rows, rows, 2, 2, 1, prediction_key="actual_ppg")
        self.assertEqual(result["mae"], 1)

    def test_evaluate_model_can_rank_by_opportunity(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "MID", 5.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES
                ('2025-26', 1, NULL, 'A', '', '', 1, 'TST', 'MID', 5.0, 10, 450, 10.0, 'a', 'test', 'now', 'test'),
                ('2025-26', 2, NULL, 'B', '', '', 1, 'TST', 'MID', 5.0, 20, 900, 10.0, 'a', 'test', 'now', 'test')
                """
            )
            for player_id, gw, points in [(1, 1, 5), (1, 2, 6), (2, 1, 7), (2, 2, 8)]:
                con.execute(
                    """
                    INSERT INTO player_gameweeks (
                      season, player_id, gameweek, fixture_id, opponent_team, was_home,
                      total_points, minutes, starts, goals_scored, assists, clean_sheets,
                      goals_conceded, saves, bonus, bps, selected, transfers_in, transfers_out,
                      value, source, fetched_at, data_period
                    ) VALUES (?, ?, ?, ?, 2, 1, ?, 90, 1, 0, 0, 0, 0, 0, 0, 0, NULL, NULL, NULL, 5.0, 'test', 'now', 'test')
                    """,
                    ("2025-26", player_id, gw, player_id * 10 + gw, points),
                )
            result = evaluate_model(con, "2025-26", "2026-27", 1, 2, 2, 1, "opportunity", "opportunity_score")
        self.assertEqual(result["model"], "opportunity")
        self.assertEqual(result["players"], 1)

    def test_tracking_round_trip_and_snapshot(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "MID", 5.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES (
                  '2026-27', 1, NULL, 'Track', '', '', 1, 'TST', 'MID',
                  5.0, 38, 3420, 10.0, 'a', 'test', 'now', 'test'
                )
                """
            )
            track_player(con, "2026-27", 1, "watch")
            self.assertEqual(tracked_players(con, "2026-27")[0]["player"], "Track")
            self.assertEqual(snapshot_tracked(con, "2026-27", gameweek=1), 1)
            self.assertEqual(snapshot_tracked(con, "2026-27", gameweek=1), 1)
            self.assertEqual(len(tracked_snapshots(con, "2026-27", 1)), 1)
            untrack_player(con, "2026-27", 1)
            self.assertEqual(tracked_players(con, "2026-27"), [])

    def test_tracked_momentum_uses_latest_two_snapshots(self):
        with connect(":memory:") as con:
            con.execute(
                """
                INSERT INTO tracked_snapshots (
                  season, player_id, gameweek, price, market_mean, value_par,
                  actual_ppg, neutral_xppg, next_3_xppg, next_6_xppg,
                  buy_delta, ownership, start_probability, status
                ) VALUES
                ('2026-27', 1, 1, 5.0, 3.0, 3.5, 3.0, 3.2, 3.2, 3.2, 0.2, 10.0, 1.0, 'WATCH'),
                ('2026-27', 1, 2, 5.0, 3.0, 3.5, 3.0, 4.0, 4.0, 4.0, 0.8, 10.0, 1.0, 'BUY')
                """
            )
            momentum = tracked_momentum(con, "2026-27")
        self.assertEqual(momentum[1]["delta_momentum"], 0.6)
        self.assertEqual(momentum[1]["tracking_status"], "IMPROVING")
        self.assertEqual(tracking_status(0.0, -0.4), "DECLINING")

    def test_squad_analysis_finds_replacement(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "MID", 5.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES
                ('2026-27', 1, NULL, 'Owned', '', '', 1, 'TST', 'MID', 5.0, 10, 900, 10.0, 'a', 'test', 'now', 'test'),
                ('2026-27', 2, NULL, 'Buy', '', '', 1, 'TST', 'MID', 5.0, 40, 900, 10.0, 'a', 'test', 'now', 'test')
                """
            )
            upsert_squad_player(con, "2026-27", 1, 4.8, 5.0)
            row = squad_analysis(con, "2026-27", bank=0.1)[0]
            remove_squad_player(con, "2026-27", 1)
        self.assertEqual(row["selling_price"], 4.9)
        self.assertEqual(row["best_replacement"], "Buy")
        self.assertGreater(row["transfer_gain"], 0)
        self.assertEqual(squad_verdict(0, 6), "SELL")

    def test_player_detail_includes_recent_history(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "MID", 5.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES (
                  '2026-27', 1, NULL, 'Detail', '', '', 1, 'TST', 'MID',
                  5.0, 10, 90, 10.0, 'a', 'test', 'now', 'test'
                )
                """
            )
            con.execute(
                """
                INSERT INTO player_gameweeks (
                  season, player_id, gameweek, fixture_id, opponent_team, was_home,
                  total_points, minutes, starts, goals_scored, assists, clean_sheets,
                  goals_conceded, saves, bonus, bps, selected, transfers_in, transfers_out,
                  value, source, fetched_at, data_period
                ) VALUES
                ('2026-27', 1, 1, 1, 2, 1, 10, 90, 1, 0, 0, 0, 0, 0, 0, 0, NULL, NULL, NULL, 5.0, 'test', 'now', 'test')
                """
            )
        detail = player_detail(con, "2026-27", 1)
        recent = recent_gameweeks(con, "2026-27", 1)
        self.assertEqual(detail["current"]["player"], "Detail")
        self.assertIn("appearance_ev", detail["projection_breakdown"])
        self.assertEqual(recent[0]["total_points"], 10)

    def test_projection_breakdown_sums_to_projection(self):
        row = {"position": "MID", "expected_minutes": 90, "neutral_xppg": 5.0, "actual_ppg": 4.0, "next_6_xppg": 5.2}
        breakdown = projection_breakdown(row)
        total = sum(breakdown[key] for key in ("appearance_ev", "attacking_ev", "clean_sheet_ev", "defcon_ev", "bonus_ev", "save_ev", "bonus_other_ev", "fixture_adjustment"))
        self.assertAlmostEqual(total, breakdown["fixture_xpts"])

    def test_goalkeeper_save_history_reaches_board(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "GK", 4.5, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES (
                  '2026-27', 1, NULL, 'Save Man', '', '', 1, 'TST', 'GK',
                  4.5, 10, 90, 10.0, 'a', 'test', 'now', 'test'
                )
                """
            )
            con.execute(
                """
                INSERT INTO player_gameweeks (
                  season, player_id, gameweek, fixture_id, opponent_team, was_home,
                  total_points, minutes, starts, goals_scored, assists, clean_sheets,
                  goals_conceded, saves, bonus, bps, selected, transfers_in, transfers_out,
                  value, source, fetched_at, data_period
                ) VALUES
                ('2026-27', 1, 1, 1, 2, 1, 6, 90, 1, 0, 0, 0, 0, 6, 0, 0, NULL, NULL, NULL, 4.5, 'test', 'now', 'test')
                """
            )
            rates = save_rates(con, "2026-27")
            row = buy_board(con, "2026-27", "2026-27", 1, 1)[0]
        self.assertGreater(rates[1], 0)
        self.assertGreater(row["save_xppg"], 0)

    def test_underlying_import_rates_and_board_usage(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "FWD", 6.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES (
                  '2026-27', 1, NULL, 'xG Man', '', '', 1, 'TST', 'FWD',
                  6.0, 10, 900, 10.0, 'a', 'test', 'now', 'test'
                )
                """
            )
            con.execute(
                """
                INSERT INTO player_gameweeks (
                  season, player_id, gameweek, fixture_id, opponent_team, was_home,
                  total_points, minutes, starts, goals_scored, assists, clean_sheets,
                  goals_conceded, saves, bonus, bps, selected, transfers_in, transfers_out,
                  value, source, fetched_at, data_period
                ) VALUES
                ('2026-27', 1, 1, 1, 2, 1, 6, 90, 1, 0, 0, 0, 0, 0, 3, 0, NULL, NULL, NULL, 6.0, 'test', 'now', 'test')
                """
            )
            count = replace_player_underlying(
                con,
                "2026-27",
                pd.DataFrame([{"player_id": 1, "gameweek": 1, "minutes": 90, "xg": 1.0, "xa": 0.5, "cbirt": 12}]),
                "test",
                "now",
            )
            rates = player_underlying_rates(con, "2026-27")
            bonus = bonus_rates(con, "2026-27")
            row = buy_board(con, "2026-27", "2026-27", 10, 1)[0]
        self.assertEqual(count, 1)
        self.assertEqual(round(attacking_xppg("FWD", 90, 1, 0.5), 2), 5.5)
        self.assertEqual(round(rates[1]["xg90"], 2), 1.0)
        self.assertEqual(round(rates[1]["cbirt90"], 2), 12.0)
        self.assertGreater(bonus[1], 0)
        self.assertEqual(row["xg90"], 1.0)
        self.assertEqual(row["defcon_xppg"], 2.0)
        self.assertGreater(row["bonus_xppg"], 0)

    def test_role_override_boosts_board_projection(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "MID", 5.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES (
                  '2026-27', 1, NULL, 'Role Man', '', '', 1, 'TST', 'MID',
                  5.0, 30, 900, 10.0, 'a', 'test', 'now', 'test'
                )
                """
            )
            before = buy_board(con, "2026-27", "2026-27", 10, 1)[0]
            add_role_override(con, "2026-27", 1, 1, 0, 1, 0, "pens and corners")
            after = buy_board(con, "2026-27", "2026-27", 10, 1)[0]
            roles = latest_role_overrides(con, "2026-27")
            history = role_history(con, "2026-27", 1)
        self.assertGreater(after["neutral_xppg"], before["neutral_xppg"])
        self.assertEqual(after["role_override_reason"], "pens and corners")
        self.assertEqual(roles[1]["corners"], 1)
        self.assertEqual(history[0]["reason"], "pens and corners")

    def test_team_underlying_drives_fixture_factor(self):
        with connect(":memory:") as con:
            con.execute("INSERT INTO app_state VALUES ('2026-27', 'current_gameweek', '1', CURRENT_TIMESTAMP)")
            con.execute("INSERT INTO fixtures VALUES ('2026-27', 1, 2, '', 1, 2, 3, 3, 0, 'test', 'now', 'test')")
            count = replace_team_underlying(
                con,
                "2026-27",
                pd.DataFrame(
                    [
                        {"team_id": 1, "gameweek": 1, "xg": 1.0, "xga": 1.0},
                        {"team_id": 2, "gameweek": 1, "xg": 1.0, "xga": 2.0},
                    ]
                ),
                "test",
                "now",
            )
            strengths = team_strengths(con, "2026-27", 1)
            factors = upcoming_fixture_factors(con, "2026-27", 1, 1)
        self.assertEqual(count, 2)
        self.assertGreater(strengths[2]["defensive_weakness"], 1)
        self.assertGreater(factors[0], 1)

    def test_expected_opponent_goals_use_team_strength(self):
        with connect(":memory:") as con:
            con.execute("INSERT INTO app_state VALUES ('2026-27', 'current_gameweek', '1', CURRENT_TIMESTAMP)")
            con.execute("INSERT INTO fixtures VALUES ('2026-27', 1, 2, '', 1, 2, 3, 3, 0, 'test', 'now', 'test')")
            replace_team_underlying(
                con,
                "2026-27",
                pd.DataFrame(
                    [
                        {"team_id": 1, "gameweek": 1, "xg": 1.0, "xga": 0.8},
                        {"team_id": 2, "gameweek": 1, "xg": 1.5, "xga": 1.2},
                    ]
                ),
                "test",
                "now",
            )
            goals = upcoming_expected_opponent_goals(con, "2026-27", 1, 1)
        self.assertLess(goals[0], 1.35 * 1.25)

    def test_buy_board_includes_clean_sheet_ev(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "DEF", 5.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute("INSERT INTO app_state VALUES ('2026-27', 'current_gameweek', '1', CURRENT_TIMESTAMP)")
            con.execute("INSERT INTO fixtures VALUES ('2026-27', 1, 2, '', 1, 2, 1, 5, 0, 'test', 'now', 'test')")
            con.execute(
                """
                INSERT INTO players VALUES (
                  '2026-27', 1, NULL, 'Clean', '', '', 1, 'TST', 'DEF',
                  5.0, 30, 900, 10.0, 'a', 'test', 'now', 'test'
                )
                """
            )
            row = buy_board(con, "2026-27", "2026-27", 10, 1)[0]
        self.assertGreater(row["clean_sheet_xppg_6"], 0)
        self.assertGreater(row["expected_opponent_goals_6"], 0)

    def test_dynamic_price_par_blends_current_curve(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "MID", 5.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES
                ('2025-26', 1, NULL, 'A', '', '', 1, 'TST', 'MID', 5.0, 50, 900, 10.0, 'a', 'test', 'now', 'test'),
                ('2025-26', 2, NULL, 'B', '', '', 1, 'TST', 'MID', 5.0, 40, 900, 10.0, 'a', 'test', 'now', 'test'),
                ('2025-26', 3, NULL, 'C', '', '', 1, 'TST', 'MID', 5.0, 30, 900, 10.0, 'a', 'test', 'now', 'test')
                """
            )
            for player_id, points in [(1, 50), (2, 40), (3, 30)]:
                con.execute(
                    """
                    INSERT INTO player_gameweeks (
                      season, player_id, gameweek, fixture_id, opponent_team, was_home,
                      total_points, minutes, starts, goals_scored, assists, clean_sheets,
                      goals_conceded, saves, bonus, bps, selected, transfers_in, transfers_out,
                      value, source, fetched_at, data_period
                    ) VALUES (?, ?, 5, ?, 2, 1, ?, 450, 1, 0, 0, 0, 0, 0, 0, 0, NULL, NULL, NULL, 5.0, 'test', 'now', 'test')
                    """,
                    ("2025-26", player_id, player_id, points),
                )
            current = current_curve_points(con, "2025-26", 5)
            mean, par, confidence = blended_par_for(con, "MID", 5.0, "2026-27", "2025-26", 5)
        self.assertTrue(current)
        self.assertGreater(mean, 3.0)
        self.assertGreater(par, 3.5)
        self.assertIn(confidence, {"LOW", "MEDIUM"})

    def test_tracked_snapshot_alerts_are_deduped_and_acknowledgeable(self):
        with connect(":memory:") as con:
            con.execute(
                """
                INSERT INTO players VALUES (
                  '2026-27', 1, NULL, 'Alert', '', '', 1, 'TST', 'MID',
                  5.0, 10, 90, 10.0, 'a', 'test', 'now', 'test'
                )
                """
            )
            con.execute(
                """
                INSERT INTO tracked_snapshots (
                  season, player_id, gameweek, price, market_mean, value_par,
                  actual_ppg, neutral_xppg, next_3_xppg, next_6_xppg,
                  buy_delta, ownership, start_probability, status
                ) VALUES
                ('2026-27', 1, 1, 5.0, 3.0, 3.5, 3.0, 3.2, 3.2, 3.2, -0.3, 10.0, 1.0, 'WATCH'),
                ('2026-27', 1, 2, 5.0, 3.0, 3.5, 3.0, 3.9, 3.9, 3.9, 0.2, 10.0, 1.0, 'BUY')
                """
            )
            self.assertEqual(generate_tracked_alerts(con, "2026-27"), 3)
            self.assertEqual(generate_tracked_alerts(con, "2026-27"), 0)
            alerts = list_alerts(con, "2026-27")
            acknowledge_alert(con, alerts[0]["id"])
            remaining = list_alerts(con, "2026-27")
        self.assertEqual(len(alerts), 3)
        self.assertEqual(len(remaining), 2)

    def test_minutes_override_changes_board_minutes(self):
        with connect(":memory:") as con:
            con.execute(
                "INSERT INTO price_par_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("2026-27", "test", "FWD", 6.0, 3.0, 3.5, 5, 0, "HIGH", "test", "now", "test"),
            )
            con.execute(
                """
                INSERT INTO players VALUES (
                  '2026-27', 1, NULL, 'Minutes', '', '', 1, 'TST', 'FWD',
                  6.0, 10, 300, 10.0, 'a', 'test', 'now', 'test'
                )
                """
            )
            before = buy_board(con, "2026-27", "2026-27", 10, 1)[0]
            add_minutes_override(con, "2026-27", 1, 0.9, 80, 0.1, 20, "starter injured")
            overrides = latest_minutes_overrides(con, "2026-27")
            after = buy_board(con, "2026-27", "2026-27", 10, 1)[0]
        self.assertEqual(round(overrides[1]["expected_minutes"], 1), 74.0)
        self.assertGreater(after["expected_minutes"], before["expected_minutes"])
        self.assertEqual(after["minutes_override_reason"], "starter injured")


if __name__ == "__main__":
    unittest.main()
