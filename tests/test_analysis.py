import unittest

import pandas as pd

from backend.data.db import connect
from backend.ingestion.loaders import replace_team_underlying, replace_understat_shots
from backend.services.analysis import HEADLINE_METRICS, benchmark_minutes, player_analysis


class AnalysisTests(unittest.TestCase):
    def test_benchmark_thresholds_are_early_season_rules(self):
        self.assertEqual([benchmark_minutes(gw) for gw in (1, 2, 3, 10)], [45, 90, 180, 180])

    def test_shot_ingestion_and_benchmarks_exclude_cameos(self):
        with connect(":memory:") as con:
            con.execute("INSERT INTO teams (season, team_id, name, short_name, source, fetched_at, data_period) VALUES ('2026-27', 1, 'Brentford', 'BRE', 'test', 'now', 'test'), ('2026-27', 2, 'Arsenal', 'ARS', 'test', 'now', 'test')")
            con.execute("INSERT INTO fixtures (season, fixture_id, gameweek, kickoff_time, team_h, team_a, team_h_difficulty, team_a_difficulty, finished, source, fetched_at, data_period) VALUES ('2026-27', 10, 1, '2026-08-20T12:00:00Z', 1, 2, 3, 3, 1, 'test', 'now', 'test')")
            con.execute("""
                INSERT INTO players (season, player_id, web_name, first_name, second_name, team_id, team, position, current_price, total_points, minutes, source, fetched_at, data_period) VALUES
                ('2026-27', 1, 'Thiago', 'Igor', 'Thiago', 1, 'Brentford', 'FWD', 8.0, 2, 90, 'test', 'now', 'test'),
                ('2026-27', 2, 'Cameo', '', 'Cameo', 1, 'Brentford', 'FWD', 7.5, 1, 5, 'test', 'now', 'test')
            """)
            con.execute("""
                INSERT INTO player_gameweeks (season, player_id, gameweek, fixture_id, minutes, total_points, source, fetched_at, data_period) VALUES
                ('2026-27', 1, 1, 10, 90, 2, 'test', 'now', 'test'),
                ('2026-27', 2, 1, 10, 5, 1, 'test', 'now', 'test')
            """)
            shots = pd.DataFrame([
                {'player': 'Igor Thiago', 'player_assisted': '', 'team': 'Brentford', 'match': 'u1', 'match_date': '2026-08-20', 'xG': 0.6, 'X': 0.9, 'Y': 0.5, 'result': 'SavedShot', 'situation': 'OpenPlay'},
                {'player': 'Cameo', 'player_assisted': 'Igor Thiago', 'team': 'Brentford', 'match': 'u1', 'match_date': '2026-08-20', 'xG': 0.1, 'X': 0.8, 'Y': 0.5, 'result': 'MissedShots', 'situation': 'OpenPlay'},
            ])
            quality = replace_understat_shots(con, '2026-27', shots, 'understat', 'now')
            self.assertEqual(quality, {'rows': 2, 'mapped_players': 2, 'unmapped_players': 0, 'unmapped_names': []})
            analysis = player_analysis(con, '2026-27', 1)
        game = analysis['games'][0]
        shot = next(item for item in game['comparisons'] if item['key'] == 'shots')
        self.assertTrue(game['benchmark_eligible'])
        self.assertEqual(shot['raw'], 1)
        self.assertEqual(shot['cohort_size'], 1)
        self.assertEqual(shot['percentile'], 50)

    def test_benchmark_uses_peer_season_to_date_rates_not_current_cameo(self):
        with connect(":memory:") as con:
            con.execute("INSERT INTO teams (season, team_id, name, short_name, source, fetched_at, data_period) VALUES ('2026-27', 1, 'A', 'A', 'test', 'now', 'test')")
            con.execute("""
                INSERT INTO players (season, player_id, web_name, team_id, team, position, current_price, total_points, minutes, source, fetched_at, data_period) VALUES
                ('2026-27', 1, 'Target', 1, 'A', 'FWD', 8.0, 0, 90, 'test', 'now', 'test'),
                ('2026-27', 2, 'Cameo', 1, 'A', 'FWD', 8.8, 0, 95, 'test', 'now', 'test'),
                ('2026-27', 3, 'Mid', 1, 'A', 'MID', 8.0, 0, 180, 'test', 'now', 'test')
            """)
            con.executemany("INSERT INTO player_gameweeks (season, player_id, gameweek, fixture_id, minutes, total_points, source, fetched_at, data_period) VALUES ('2026-27', ?, ?, ?, ?, 0, 'test', 'now', 'test')", [
                (1, 1, 11, 40), (1, 2, 12, 50), (2, 1, 11, 90), (2, 2, 12, 5), (3, 1, 11, 90), (3, 2, 12, 90),
            ])
            con.executemany("""
                INSERT INTO player_shot_gameweeks (season, player_id, gameweek, fixture_id, provider_match_id, shots, xg, source, fetched_at, data_period)
                VALUES ('2026-27', ?, ?, ?, ?, ?, ?, 'understat', 'now', 'test')
            """, [
                (1, 1, 11, 'a1', 1, 0.1), (1, 2, 12, 'a2', 1, 0.5),
                (2, 1, 11, 'b1', 2, 0.2), (2, 2, 12, 'b2', 10, 1.0),
                (3, 1, 11, 'c1', 100, 10.0), (3, 2, 12, 'c2', 100, 10.0),
            ])
            analysis = player_analysis(con, '2026-27', 1)
            games = analysis['games']
        self.assertFalse(games[0]['benchmark_eligible'])
        self.assertTrue(games[1]['benchmark_eligible'])
        shots = next(item for item in games[1]['comparisons'] if item['key'] == 'shots')
        self.assertEqual(shots['cohort_size'], 2)
        self.assertEqual(shots['positional_average'], 6.68)  # target 2/90 and peer 12/95, not peer's 10/5 cameo
        self.assertEqual(shots['price_band'], 1.0)
        self.assertEqual(shots['price_average'], 6.68)
        xg_per_shot = next(item for item in games[1]['comparisons'] if item['key'] == 'xg_per_shot')
        self.assertEqual(xg_per_shot['raw'], 0.5)
        aggregate_shots = next(item for item in analysis['aggregate']['comparisons'] if item['key'] == 'shots')
        self.assertEqual((analysis['aggregate']['cohort_size'], analysis['aggregate']['price_band']), (2, 1.0))
        self.assertEqual((aggregate_shots['raw'], aggregate_shots['positional_average']), (2.0, 6.68))

    def test_default_last_five_and_explicit_season_aggregate_windows(self):
        with connect(":memory:") as con:
            con.execute("INSERT INTO players (season, player_id, web_name, team_id, team, position, current_price, total_points, minutes, source, fetched_at, data_period) VALUES ('2026-27', 1, 'Window', 1, 'A', 'FWD', 8, 0, 540, 'test', 'now', 'test')")
            for gameweek in range(1, 7):
                con.execute("INSERT INTO player_gameweeks (season, player_id, gameweek, fixture_id, minutes, total_points, source, fetched_at, data_period) VALUES ('2026-27', 1, ?, ?, 90, 0, 'test', 'now', 'test')", (gameweek, gameweek))
                con.execute("INSERT INTO player_shot_gameweeks (season, player_id, gameweek, fixture_id, provider_match_id, shots, xg, source, fetched_at, data_period) VALUES ('2026-27', 1, ?, ?, ?, ?, ?, 'understat', 'now', 'test')", (gameweek, gameweek, str(gameweek), 10 if gameweek == 1 else 1, 1 if gameweek == 1 else .1))
            automatic = player_analysis(con, '2026-27', 1)
            season = player_analysis(con, '2026-27', 1, 'season')
        self.assertEqual((automatic['aggregate']['window'], automatic['aggregate']['appearances'], automatic['aggregate']['from_gameweek']), ('last5', 5, 2))
        self.assertEqual(automatic['aggregate']['available_windows'], ['season', 'last5'])
        self.assertEqual(next(item for item in automatic['aggregate']['comparisons'] if item['key'] == 'shots')['raw'], 1.0)
        self.assertEqual(next(item for item in season['aggregate']['comparisons'] if item['key'] == 'shots')['raw'], 2.5)

    def test_unmapped_understat_player_is_reported_and_evidence_stays_null(self):
        with connect(":memory:") as con:
            con.execute("INSERT INTO teams (season, team_id, name, short_name, source, fetched_at, data_period) VALUES ('2026-27', 1, 'A', 'A', 'test', 'now', 'test'), ('2026-27', 2, 'B', 'B', 'test', 'now', 'test')")
            con.execute("INSERT INTO fixtures (season, fixture_id, gameweek, kickoff_time, team_h, team_a, team_h_difficulty, team_a_difficulty, finished, source, fetched_at, data_period) VALUES ('2026-27', 1, 1, '2026-08-01T12:00:00Z', 1, 2, 3, 3, 1, 'test', 'now', 'test')")
            con.execute("INSERT INTO players (season, player_id, web_name, team_id, team, position, current_price, total_points, minutes, source, fetched_at, data_period) VALUES ('2026-27', 1, 'Known', 1, 'A', 'FWD', 7.0, 0, 90, 'test', 'now', 'test')")
            con.execute("INSERT INTO player_gameweeks (season, player_id, gameweek, fixture_id, minutes, total_points, source, fetched_at, data_period) VALUES ('2026-27', 1, 1, 1, 90, 2, 'test', 'now', 'test')")
            quality = replace_understat_shots(con, '2026-27', pd.DataFrame([{'player': 'Unknown', 'team': 'A', 'match': 'u1', 'match_date': '2026-08-01', 'xG': .4, 'X': .9, 'Y': .5, 'result': 'SavedShot', 'situation': 'OpenPlay'}]), 'understat', 'now')
            game = player_analysis(con, '2026-27', 1)['games'][0]
        self.assertEqual(quality['mapped_players'], 0)
        self.assertEqual(quality['unmapped_players'], 1)
        self.assertEqual(quality['rows'], 0)
        self.assertIsNone(game['shots'])
        self.assertNotIn('shots', {item['key'] for item in game['comparisons']})

    def test_match_shots_supply_gk_workload_and_save_percentage(self):
        with connect(":memory:") as con:
            con.execute("INSERT INTO teams (season, team_id, name, short_name, source, fetched_at, data_period) VALUES ('2026-27', 1, 'A', 'A', 'test', 'now', 'test'), ('2026-27', 2, 'B', 'B', 'test', 'now', 'test')")
            con.execute("INSERT INTO fixtures (season, fixture_id, gameweek, kickoff_time, team_h, team_a, team_h_difficulty, team_a_difficulty, finished, source, fetched_at, data_period) VALUES ('2026-27', 1, 1, '2026-08-01T12:00:00Z', 1, 2, 3, 3, 1, 'test', 'now', 'test')")
            con.execute("INSERT INTO players (season, player_id, web_name, first_name, second_name, team_id, team, position, current_price, total_points, minutes, source, fetched_at, data_period) VALUES ('2026-27', 1, 'Shooter', '', 'Shooter', 1, 'A', 'FWD', 7, 0, 90, 'test', 'now', 'test'), ('2026-27', 2, 'Keeper', '', 'Keeper', 2, 'B', 'GK', 5, 0, 90, 'test', 'now', 'test')")
            con.execute("INSERT INTO player_gameweeks (season, player_id, gameweek, fixture_id, minutes, total_points, saves, goals_conceded, source, fetched_at, data_period) VALUES ('2026-27', 2, 1, 1, 90, 3, 3, 1, 'test', 'now', 'test')")
            replace_team_underlying(con, '2026-27', pd.DataFrame([{'team_id': 1, 'gameweek': 1, 'xg': 1, 'xga': 1}, {'team_id': 2, 'gameweek': 1, 'xg': 1, 'xga': 1}]), 'understat', 'now')
            shots = pd.DataFrame([{'player': 'Shooter', 'team': 'A', 'opponent': 'B', 'match': 'u1', 'match_date': '2026-08-01', 'xG': .1, 'X': .9, 'Y': .5, 'result': result, 'situation': 'OpenPlay'} for result in ('SavedShot', 'SavedShot', 'SavedShot', 'Goal')])
            replace_understat_shots(con, '2026-27', shots, 'understat', 'now')
            game = player_analysis(con, '2026-27', 2)['games'][0]
        self.assertEqual((game['shots_faced'], game['shots_on_target_faced']), (4, 4))
        save_percentage = next(item for item in game['comparisons'] if item['key'] == 'save_percentage')
        self.assertEqual(save_percentage['raw'], 75.0)

    def test_dgw_is_one_evidence_card_and_performance_points_reconcile(self):
        with connect(":memory:") as con:
            con.execute("INSERT INTO teams (season, team_id, name, short_name, source, fetched_at, data_period) VALUES ('2026-27', 1, 'A', 'A', 'test', 'now', 'test'), ('2026-27', 2, 'B', 'B', 'test', 'now', 'test'), ('2026-27', 3, 'C', 'C', 'test', 'now', 'test')")
            con.execute("INSERT INTO fixtures (season, fixture_id, gameweek, kickoff_time, team_h, team_a, team_h_difficulty, team_a_difficulty, finished, source, fetched_at, data_period) VALUES ('2026-27', 11, 1, '2026-08-01', 1, 2, 3, 3, 1, 'test', 'now', 'test'), ('2026-27', 12, 1, '2026-08-04', 3, 1, 3, 3, 1, 'test', 'now', 'test')")
            con.execute("INSERT INTO players (season, player_id, web_name, team_id, team, position, current_price, total_points, minutes, source, fetched_at, data_period) VALUES ('2026-27', 1, 'Double', 1, 'A', 'FWD', 8.0, 7, 90, 'test', 'now', 'test')")
            con.execute("INSERT INTO player_gameweeks (season, player_id, gameweek, fixture_id, minutes, total_points, source, fetched_at, data_period) VALUES ('2026-27', 1, 1, 11, 60, 2, 'test', 'now', 'test'), ('2026-27', 1, 1, 12, 30, 5, 'test', 'now', 'test')")
            con.execute("INSERT INTO game_underlying_xpts (season, player_id, gameweek, source, minutes, game_underlying_xpts, fetched_at, data_period) VALUES ('2026-27', 1, 1, 'test', 90, 4.0, 'now', 'test')")
            con.execute("INSERT INTO current_player_metrics (season, player_id, player, team, team_id, position, current_price, actual_ppg, current_par, underlying_xppg, performance_delta, performance_data_state) VALUES ('2026-27', 1, 'Double', 'A', 1, 'FWD', 8.0, 7.0, 3.0, 4.0, 1.0, 'sufficient')")
            analysis = player_analysis(con, '2026-27', 1)
        self.assertEqual(len(analysis['games']), 1)
        self.assertEqual((analysis['games'][0]['minutes'], analysis['games'][0]['points']), (90, 7))
        self.assertEqual(analysis['games'][0]['opponent'], 'B (H), C (A)')
        self.assertEqual(analysis['games'][0]['performance_points'], 4.0)
        self.assertEqual(analysis['games'][0]['cumulative_performance_ppg'], analysis['headline']['performance_ppg'])
        self.assertEqual(analysis['aggregate']['appearances'], 1)
        self.assertEqual(sum(game['minutes'] for game in analysis['games']), analysis['aggregate']['minutes'])

    def test_dgw_team_evidence_is_aggregated_not_overwritten(self):
        with connect(":memory:") as con:
            con.execute("INSERT INTO team_underlying_gameweeks (season, team_id, gameweek, xg, xga, source, fetched_at, data_period) VALUES ('2026-27', 1, 3, 99, 99, 'stale-cache', 'old', 'test')")
            count = replace_team_underlying(con, '2026-27', pd.DataFrame([
                {'team_id': 1, 'gameweek': 3, 'is_home': 1, 'xg': 1.2, 'xga': .8, 'shots_conceded': 7, 'shots_on_target_conceded': 3},
                {'team_id': 1, 'gameweek': 3, 'is_home': 0, 'xg': .9, 'xga': 1.1, 'shots_conceded': 10, 'shots_on_target_conceded': 4},
            ]), 'understat', 'now')
            row = con.execute("SELECT is_home, xg, xga, shots_conceded, shots_on_target_conceded FROM team_underlying_gameweeks").fetchone()
            stored = con.execute("SELECT COUNT(*) AS n FROM team_underlying_gameweeks").fetchone()['n']
        self.assertEqual(count, 1)
        self.assertEqual(stored, 1)
        self.assertEqual((row['is_home'], row['shots_conceded'], row['shots_on_target_conceded']), (None, 17, 7))
        self.assertAlmostEqual(row['xg'], 2.1)
        self.assertAlmostEqual(row['xga'], 1.9)

    def test_negative_performance_delta_is_price_language(self):
        with connect(":memory:") as con:
            con.execute("INSERT INTO players (season, player_id, web_name, team_id, team, position, current_price, total_points, minutes, source, fetched_at, data_period) VALUES ('2026-27', 1, 'Low', 1, 'A', 'DEF', 5.0, 4, 180, 'test', 'now', 'test')")
            con.execute("INSERT INTO current_player_metrics (season, player_id, player, position, current_price, actual_ppg, current_par, underlying_xppg, performance_delta, performance_data_state) VALUES ('2026-27', 1, 'Low', 'DEF', 5.0, 2.0, 4.0, 3.0, -1.0, 'sufficient')")
            analysis = player_analysis(con, '2026-27', 1)
        self.assertIn('Underlying performance below price expectation', analysis['diagnosis'])
        self.assertNotIn('positional benchmark', analysis['diagnosis'])

    def test_position_headlines_are_distinct(self):
        self.assertNotEqual(HEADLINE_METRICS['DEF'], HEADLINE_METRICS['MID'])
        self.assertNotEqual(HEADLINE_METRICS['MID'], HEADLINE_METRICS['FWD'])
        self.assertEqual(HEADLINE_METRICS['GK'][0], 'saves')


if __name__ == "__main__":
    unittest.main()
