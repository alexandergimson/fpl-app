import unittest

from backend.models.price_par import ParPoint, interpolate, pava
from backend.models.projections import clean_sheet_ev, defcon_ev, expected_minutes
from backend.models.projections import projection_breakdown
import pandas as pd
from backend.services.valuation import player_status, selling_price
from backend.services.boards import breakout_board, buy_board, infer_gameweeks, trap_board
from backend.data.db import connect
from backend.services.fixtures import adjusted_horizon_ppg, upcoming_fixture_factors
from backend.services.history import future_points, player_totals_as_of
from backend.backtests.metrics import evaluate_rows, mae, ranks, rmse, spearman
from backend.services.tracking import snapshot_tracked, track_player, tracked_players, tracked_snapshots, untrack_player
from backend.services.squad import remove_squad_player, squad_analysis, squad_verdict, upsert_squad_player
from backend.services.player_detail import player_detail, recent_gameweeks
from backend.ingestion.loaders import replace_player_underlying
from backend.ingestion.loaders import replace_team_underlying
from backend.services.underlying import attacking_xppg, player_underlying_rates
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

    def test_expected_minutes(self):
        self.assertAlmostEqual(expected_minutes(0.8, 75, 0.15, 20), 63)

    def test_clean_sheet_poisson(self):
        self.assertAlmostEqual(clean_sheet_ev(1.0, 4, 1.0), 1.4715, places=3)

    def test_defcon_cap(self):
        self.assertEqual(defcon_ev(2), 2)

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
        total = sum(breakdown[key] for key in ("appearance_ev", "attacking_ev", "clean_sheet_ev", "bonus_other_ev", "fixture_adjustment"))
        self.assertAlmostEqual(total, breakdown["fixture_xpts"])

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
            count = replace_player_underlying(
                con,
                "2026-27",
                pd.DataFrame([{"player_id": 1, "gameweek": 1, "minutes": 90, "xg": 1.0, "xa": 0.5}]),
                "test",
                "now",
            )
            rates = player_underlying_rates(con, "2026-27")
            row = buy_board(con, "2026-27", "2026-27", 10, 1)[0]
        self.assertEqual(count, 1)
        self.assertEqual(round(attacking_xppg("FWD", 90, 1, 0.5), 2), 5.5)
        self.assertEqual(round(rates[1]["xg90"], 2), 1.0)
        self.assertEqual(row["xg90"], 1.0)

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


if __name__ == "__main__":
    unittest.main()
