import unittest

import pandas as pd

from backend.data.db import connect
from backend.ingestion.loaders import replace_understat_shots
from backend.services.analysis import benchmark_minutes, player_analysis


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
            self.assertEqual(replace_understat_shots(con, '2026-27', shots, 'understat', 'now'), 2)
            analysis = player_analysis(con, '2026-27', 1)
        game = analysis['games'][0]
        shot = next(item for item in game['comparisons'] if item['key'] == 'shots')
        self.assertTrue(game['benchmark_eligible'])
        self.assertEqual(shot['raw'], 1)
        self.assertEqual(shot['cohort_size'], 1)
        self.assertEqual(shot['percentile'], 50)


if __name__ == "__main__":
    unittest.main()
