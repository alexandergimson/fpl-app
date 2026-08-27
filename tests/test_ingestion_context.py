import unittest

import pandas as pd

from backend.ingestion.context import build_fpl_context
from backend.ingestion.derived_metrics import blank_gameweeks, double_gameweeks, net_transfers
from backend.ingestion.mappers import map_understat_players
from backend.ingestion.normalizers import availability_percent, normalise_player, normalise_shot, price
from backend.ingestion.providers import Dataset


class FakeFpl:
    def bootstrap(self, season):
        elements = pd.DataFrame(
            [
                {
                    "id": 1,
                    "web_name": "Saka",
                    "first_name": "Bukayo",
                    "second_name": "Saka",
                    "team": 1,
                    "element_type": 3,
                    "now_cost": 95,
                    "selected_by_percent": "55.5",
                    "status": "a",
                    "chance_of_playing_this_round": None,
                    "chance_of_playing_next_round": None,
                    "news": "",
                    "minutes": 180,
                    "starts": 2,
                    "total_points": 12,
                    "points_per_game": "6.0",
                    "form": "5.0",
                    "ep_this": "4.4",
                    "ep_next": "4.8",
                    "bps": 30,
                    "ict_index": "20.0",
                    "influence": "10.0",
                    "creativity": "5.0",
                    "threat": "5.0",
                    "goals_scored": 1,
                    "assists": 1,
                    "expected_goals": "0.8",
                    "expected_assists": "0.4",
                    "expected_goal_involvements": "1.2",
                    "expected_goals_per_90": "0.4",
                    "expected_assists_per_90": "0.2",
                    "expected_goal_involvements_per_90": "0.6",
                    "transfers_in_event": 100,
                    "transfers_out_event": 40,
                }
            ]
        )
        elements.attrs["teams"] = pd.DataFrame([{"id": 1, "name": "Arsenal", "short_name": "ARS"}])
        elements.attrs["current_gameweek"] = 1
        return Dataset(elements, "fake", "now", season)

    def fixtures(self, season):
        return Dataset(
            pd.DataFrame(
                [
                    {"id": 1, "event": 1, "team_h": 1, "team_a": 2, "kickoff_time": "2026-08-15T12:30:00Z", "team_h_score": 2, "team_a_score": 0, "team_h_difficulty": 2, "team_a_difficulty": 4, "finished": True, "started": True},
                    {"id": 2, "event": 2, "team_h": 1, "team_a": 3, "kickoff_time": "2026-08-22T12:30:00Z", "team_h_score": None, "team_a_score": None, "team_h_difficulty": 3, "team_a_difficulty": 3, "finished": False, "started": False},
                    {"id": 3, "event": 2, "team_h": 4, "team_a": 1, "kickoff_time": "2026-08-25T12:30:00Z", "team_h_score": None, "team_a_score": None, "team_h_difficulty": 3, "team_a_difficulty": 3, "finished": False, "started": False},
                ]
            ),
            "fake",
            "now",
            season,
        )

    def entry_picks(self, manager_id, gameweek, season):
        picks = pd.DataFrame([{"element": 1, "purchase_price": 90, "selling_price": 93, "is_captain": True, "is_vice_captain": False}])
        picks.attrs["entry_history"] = {"bank": 15, "value": 1005, "transfers": 1, "event_transfers_cost": 4, "overall_rank": 123, "current_event": gameweek}
        return Dataset(picks, "fake", "now", season)

    def entry_transfers(self, manager_id, season):
        return Dataset(pd.DataFrame([{"element_in": 1, "element_out": 2}]), "fake", "now", season)

    def element_summary(self, player_id, season):
        return Dataset(pd.DataFrame([{"minutes": 90}, {"minutes": 0}, {"minutes": 60}]), "fake", "now", season)


class FakeUnderstat:
    def shots(self, season):
        return Dataset(pd.DataFrame([{"player": "Saka", "team": "Arsenal", "opponent": "Chelsea", "minute": 10, "xG": 0.4, "X": 0.9, "Y": 0.5, "result": "Goal", "situation": "OpenPlay", "player_assisted": "Odegaard"}]), "fake", "now", season)


class IngestionContextTests(unittest.TestCase):
    def test_price_availability_position_and_transfers(self):
        self.assertEqual(price(95), 9.5)
        self.assertEqual(availability_percent("a", None), 100)
        player = normalise_player({"id": 1, "web_name": "Saka", "team": 1, "element_type": 3, "now_cost": 95, "status": "a", "transfers_in_event": 10, "transfers_out_event": 4}, {1: {"name": "Arsenal"}}, [{"minutes": 90}])
        self.assertEqual(player["position"], "MID")
        self.assertEqual(player["current_price"], 9.5)
        self.assertEqual(player["net_transfers"], 6)
        self.assertEqual(net_transfers(10, 4), 6)

    def test_blank_double_and_shot_derivations(self):
        fixtures = [{"event": 1, "team_h": 1, "team_a": 2}, {"event": 1, "team_h": 3, "team_a": 1}, {"event": 2, "team_h": 2, "team_a": 3}]
        self.assertEqual(double_gameweeks(fixtures, [1], [1, 2])[1], [1])
        self.assertEqual(blank_gameweeks(fixtures, [1], [1, 2])[1], [2])
        shot = normalise_shot({"player": "Saka", "team": "Arsenal", "opponent": "Chelsea", "xG": 0.4, "X": 0.9, "Y": 0.5})
        self.assertTrue(shot["shots_in_box"])
        self.assertTrue(shot["high_quality_chance"])

    def test_understat_player_mapping_uses_saka_exact_name_team(self):
        mapped = map_understat_players([{"player_id": 7, "player_name": "Bukayo Saka", "team_name": "Arsenal"}], [{"id": "u7", "player_name": "Bukayo Saka", "team": "Arsenal"}])
        self.assertEqual(mapped["u7"], 7)

    def test_build_fpl_context_outputs_normalised_records(self):
        context = build_fpl_context(123, "2026-27", FakeFpl(), FakeUnderstat())
        self.assertEqual(context["players"][0]["player_name"], "Saka")
        self.assertEqual(context["players"][0]["shots_in_box"], 1)
        self.assertEqual(context["manager"]["purchase_prices"][1], 9.0)
        self.assertEqual(context["teams"][0]["double_gw"], [2])
        self.assertEqual(context["shots"][0]["high_quality_chance"], True)


if __name__ == "__main__":
    unittest.main()
