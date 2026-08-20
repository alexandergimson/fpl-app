from __future__ import annotations

import sqlite3

from backend.services.team_strength import team_strengths
from backend.models.projections import clean_sheet_ev


def current_gameweek(con: sqlite3.Connection, season: str) -> int:
    row = con.execute("SELECT value FROM app_state WHERE season = ? AND key = 'current_gameweek'", (season,)).fetchone()
    return int(row["value"]) if row else 0


def upcoming_fixture_factors(con: sqlite3.Connection, season: str, team_id: int | None, horizon: int, start_gw: int | None = None) -> list[float]:
    if team_id is None:
        return []
    start = current_gameweek(con, season) if start_gw is None else start_gw
    rows = con.execute(
        """
        SELECT team_h, team_a, team_h_difficulty, team_a_difficulty
        FROM fixtures
        WHERE season = ?
          AND gameweek IS NOT NULL
          AND gameweek > ?
          AND (team_h = ? OR team_a = ?)
        ORDER BY gameweek, fixture_id
        LIMIT ?
        """,
        (season, start, team_id, team_id, horizon),
    ).fetchall()
    strengths = team_strengths(con, season, start)
    factors = []
    for row in rows:
        opponent_id = row["team_a"] if row["team_h"] == team_id else row["team_h"]
        opponent = strengths.get(opponent_id)
        if opponent:
            factors.append(max(0.84, min(1.16, opponent["defensive_weakness"])))
        else:
            difficulty = row["team_h_difficulty"] if row["team_h"] == team_id else row["team_a_difficulty"]
            factors.append(max(0.84, min(1.16, 1 + (3 - difficulty) * 0.08)))
    return factors


def adjusted_horizon_ppg(neutral_xppg: float, factors: list[float], horizon: int) -> float:
    if not factors:
        return neutral_xppg
    padded = factors + [1.0] * max(0, horizon - len(factors))
    return neutral_xppg * sum(padded[:horizon]) / horizon


def upcoming_expected_opponent_goals(con: sqlite3.Connection, season: str, team_id: int | None, horizon: int, start_gw: int | None = None) -> list[float]:
    if team_id is None:
        return []
    start = current_gameweek(con, season) if start_gw is None else start_gw
    rows = con.execute(
        """
        SELECT team_h, team_a, team_h_difficulty, team_a_difficulty
        FROM fixtures
        WHERE season = ?
          AND gameweek IS NOT NULL
          AND gameweek > ?
          AND (team_h = ? OR team_a = ?)
        ORDER BY gameweek, fixture_id
        LIMIT ?
        """,
        (season, start, team_id, team_id, horizon),
    ).fetchall()
    strengths = team_strengths(con, season, start)
    own = strengths.get(team_id, {})
    goals = []
    for row in rows:
        opponent_id = row["team_a"] if row["team_h"] == team_id else row["team_h"]
        opponent = strengths.get(opponent_id)
        if opponent:
            goals.append(max(0.6, min(2.4, 1.35 * opponent["attack"] * own.get("defensive_weakness", 1.0))))
        else:
            difficulty = row["team_h_difficulty"] if row["team_h"] == team_id else row["team_a_difficulty"]
            goals.append(max(0.6, min(2.4, 1.35 * (1 + (difficulty - 3) * 0.12))))
    return goals


def clean_sheet_points(position: str) -> int:
    return 4 if position in {"GK", "DEF"} else 1 if position == "MID" else 0


def clean_sheet_horizon_ev(expected_goals: list[float], position: str, expected_minutes: float, horizon: int) -> float:
    points = clean_sheet_points(position)
    if not points:
        return 0.0
    probability_of_60 = max(0.0, min(1.0, expected_minutes / 60))
    padded = expected_goals + [1.35] * max(0, horizon - len(expected_goals))
    return sum(clean_sheet_ev(xg, points, probability_of_60) for xg in padded[:horizon]) / horizon
