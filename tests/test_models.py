import unittest

from backend.models.price_par import ParPoint, interpolate, pava
from backend.models.projections import clean_sheet_ev, defcon_ev, expected_minutes
from backend.services.valuation import player_status, selling_price


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


if __name__ == "__main__":
    unittest.main()
