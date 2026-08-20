from __future__ import annotations

import sqlite3

from backend.services.team_strength import team_strengths


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
