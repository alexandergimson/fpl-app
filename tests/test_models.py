import unittest

from backend.models.price_par import ParPoint, interpolate, pava
from backend.models.projections import clean_sheet_ev, defcon_ev, expected_minutes
from backend.services.valuation import player_status, selling_price
from backend.services.boards import buy_board, infer_gameweeks
from backend.data.db import connect


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


if __name__ == "__main__":
    unittest.main()
