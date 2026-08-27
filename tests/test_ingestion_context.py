import unittest

import pandas as pd

from backend.ingestion.context import build_fpl_context
from backend.ingestion.derived_metrics import blank_gameweeks, double_gameweeks, net_transfers
from backend.ingestion.mappers import map_understat_players
from backend.ingestion.normalizers import availability_percent, normalise_player, normalise_shot, price
from backend.ingestion.providers import Dataset, OfficialFplProvider, UnderstatProvider


class FakeFpl:
    summaries = 0

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
                    "cost_change_event": 1,
                    "cost_change_start": 5,
                    "price_change_percent": "12.5",
                    "price_change_hourly_rate": "0.2",
                    "price_change_projections": [{"offset": 1}],
                    "price_change_locked_until": "2026-08-30T00:00:00Z",
                    "price_change_calibrating": False,
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
        elements.attrs["next_gameweek"] = 2
        elements.attrs["next_deadline"] = "2026-08-22T10:00:00Z"
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
        picks = pd.DataFrame([{"element": 1, "is_captain": True, "is_vice_captain": False}])
        picks.attrs["entry_history"] = {"transfers": 1, "event_transfers_cost": 4, "overall_rank": 123, "current_event": gameweek, "next_event": 2}
        return Dataset(picks, "fake", "now", season)

    def entry_history(self, manager_id, season):
        history = pd.DataFrame([{"event": 1}])
        history.attrs["chips"] = [{"name": "wildcard"}, {"name": "3xc"}]
        return Dataset(history, "fake", "now", season)

    def entry_transfers(self, manager_id, season):
        return Dataset(pd.DataFrame([{"element_in": 1, "element_out": 2}]), "fake", "now", season)

    def element_summary(self, player_id, season):
        self.summaries += 1
        return Dataset(pd.DataFrame([{"minutes": 90}, {"minutes": 0}, {"minutes": 60}]), "fake", "now", season)

    def my_team(self, manager_id, season):
        picks = pd.DataFrame([{"element": 1, "purchase_price": 90, "selling_price": 93, "is_captain": True, "is_vice_captain": False}])
        picks.attrs["transfers"] = {"bank": 15, "value": 1005, "free_transfers": 1}
        return Dataset(picks, "fake", "now", season)


class FakeUnderstat:
    def shots(self, season):
        return Dataset(pd.DataFrame([{"player": "Bukayo Saka", "team": "Arsenal", "opponent": "Chelsea", "minute": 10, "xG": 0.4, "X": 0.9, "Y": 0.5, "result": "Goal", "situation": "OpenPlay", "player_assisted": "Odegaard"}]), "fake", "now", season)

    def team_underlying(self, season, teams, fixtures):
        return Dataset(pd.DataFrame([{"team_id": 1, "gameweek": 1, "xg": 1.8, "xga": 0.6}, {"team_id": 1, "gameweek": 2, "xg": 1.2, "xga": 1.1}]), "fake", "now", season)


class RealUnderstatFixture(UnderstatProvider):
    def _json(self, season):
        return {"dates": [{"id": "m1", "isResult": True, "h": {"title": "Arsenal"}, "a": {"title": "Chelsea"}}]}, "fake", "now"

    def _match_json(self, match_id):
        return {"h": [{"player": "Saka", "minute": "10", "xG": "0.40", "X": "0.90", "Y": "0.50", "result": "Goal", "situation": "OpenPlay", "player_assisted": "Odegaard"}], "a": []}, "fake", "now"


class RealFplFixture(OfficialFplProvider):
    def _json(self, url, cache_name):
        return {
            "elements": [{"id": 1, "web_name": "Saka", "team": 1, "element_type": 3, "now_cost": 95, "status": "a"}],
            "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS"}],
            "events": [
                {"id": 1, "finished": True, "is_current": False, "is_next": False, "deadline_time": "old"},
                {"id": 2, "finished": False, "is_current": True, "is_next": False, "deadline_time": "current"},
                {"id": 3, "finished": False, "is_current": False, "is_next": True, "deadline_time": "next"},
            ],
        }, "fake", "now"


class IngestionContextTests(unittest.TestCase):
    def test_price_availability_position_and_transfers(self):
        self.assertEqual(price(95), 9.5)
        self.assertEqual(availability_percent("a", None), 100)
        player = normalise_player({"id": 1, "web_name": "Saka", "team": 1, "element_type": 3, "now_cost": 95, "status": "a", "transfers_in_event": 10, "transfers_out_event": 4}, {1: {"name": "Arsenal"}}, [{"minutes": 90}])
        self.assertEqual(player["position"], "MID")
        self.assertEqual(player["current_price"], 9.5)
        self.assertEqual(player["net_transfers"], 6)
        self.assertEqual(net_transfers(10, 4), 6)

    def test_player_price_change_fields_are_fpl_native(self):
        player = normalise_player({"id": 1, "web_name": "Saka", "team": 1, "element_type": 3, "now_cost": 95, "cost_change_event": 1, "cost_change_start": 5, "price_change_percent": "12.5", "price_change_hourly_rate": "0.2", "price_change_projections": [{"offset": 1}], "price_change_locked_until": "lock", "price_change_calibrating": True}, {1: {"name": "Arsenal"}})
        self.assertEqual(player["price_change_event"], 0.1)
        self.assertEqual(player["price_change_season"], 0.5)
        self.assertEqual(player["price_change_percent"], 12.5)
        self.assertEqual(player["price_change_projections"], [{"offset": 1}])

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
        fpl = FakeFpl()
        context = build_fpl_context(123, "2026-27", fpl, FakeUnderstat())
        self.assertEqual(context["players"][0]["player_name"], "Saka")
        self.assertEqual(context["players"][0]["shots_in_box"], 1)
        self.assertEqual(context["players"][0]["next_5_fixtures"][0]["opponent"], None)
        self.assertEqual(context["manager"]["purchase_prices"], {})
        self.assertIsNone(context["manager"]["free_transfers"])
        self.assertEqual(context["manager"]["chips_remaining"], ["bboost", "freehit", "wildcard"])
        self.assertEqual(context["teams"][0]["double_gw"], [2])
        self.assertEqual(context["teams"][0]["team_xg"], 3.0)
        self.assertEqual(context["teams"][0]["team_xga"], 1.7)
        self.assertEqual(context["current_gw"], 1)
        self.assertEqual(context["next_gw"], 2)
        self.assertEqual(context["gw_deadline"], "2026-08-22T10:00:00Z")
        self.assertEqual(context["shots"][0]["high_quality_chance"], True)
        self.assertEqual(fpl.summaries, 1)

    def test_context_maps_understat_full_name_shots_to_fpl_player_id(self):
        context = build_fpl_context(123, "2026-27", FakeFpl(), FakeUnderstat())
        saka = context["players"][0]
        self.assertEqual(saka["player_name"], "Saka")
        self.assertEqual(saka["shots"], 1)
        self.assertEqual(saka["high_quality_chances"], 1)

    def test_authenticated_context_has_private_economics(self):
        context = build_fpl_context(123, "2026-27", FakeFpl(), FakeUnderstat(), authenticated=True)
        self.assertEqual(context["manager"]["context_type"], "authenticated")
        self.assertEqual(context["manager"]["purchase_prices"][1], 9.0)
        self.assertEqual(context["manager"]["selling_prices"][1], 9.3)
        self.assertEqual(context["manager"]["free_transfers"], 1)
        self.assertEqual(context["manager"]["chips_remaining"], ["bboost", "freehit", "wildcard"])

    def test_real_understat_provider_exposes_shot_rows(self):
        dataset = RealUnderstatFixture().shots("2026-27")
        row = dataset.frame.iloc[0]
        self.assertEqual(row["player"], "Saka")
        self.assertEqual(row["team"], "Arsenal")
        self.assertEqual(row["opponent"], "Chelsea")
        self.assertGreater(row["xG"], 0)

    def test_fpl_provider_uses_current_and_next_events(self):
        dataset = RealFplFixture().bootstrap("2026-27")
        self.assertEqual(dataset.frame.attrs["current_gameweek"], 2)
        self.assertEqual(dataset.frame.attrs["next_gameweek"], 3)
        self.assertEqual(dataset.frame.attrs["next_deadline"], "next")


if __name__ == "__main__":
    unittest.main()
