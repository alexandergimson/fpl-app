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


def clean_sheet_horizon_ev(expected_goals: list[float], position: str, expected_minutes: float, horizon: int, p60: float | None = None) -> float:
    points = clean_sheet_points(position)
    if not points:
        return 0.0
    probability_of_60 = max(0.0, min(1.0, expected_minutes / 60)) if p60 is None else max(0.0, min(1.0, p60))
    padded = expected_goals + [1.35] * max(0, horizon - len(expected_goals))
    return sum(clean_sheet_ev(xg, points, probability_of_60) for xg in padded[:horizon]) / horizon


def project_fixture_xpts(
    position: str,
    expected_minutes: float,
    probability_of_60_value: float,
    xg90: float,
    xa90: float,
    cbit90: float,
    cbirt90: float,
    bonus_ev: float,
    save_ev: float,
    attack_factor: float,
    expected_goals_against: float,
) -> dict[str, float]:
    minutes_share = max(0.0, expected_minutes) / 90
    goal_points = 6 if position in {"GK", "DEF"} else 5 if position == "MID" else 4
    threshold = 10 if position == "DEF" else 12 if position in {"MID", "FWD"} else 0
    actions = cbit90 if position == "DEF" else cbirt90
    defcon = 0.0 if not threshold or actions <= 0 else min(1.0, expected_minutes / 60) * max(0.0, min(1.0, actions / threshold)) * 2
    clean = clean_sheet_horizon_ev([expected_goals_against], position, expected_minutes, 1, probability_of_60_value)
    result = {
        "appearance_ev": min(2.0, 2.0 * minutes_share),
        "goal_ev": minutes_share * max(0.0, xg90) * attack_factor * goal_points,
        "assist_ev": minutes_share * max(0.0, xa90) * attack_factor * 3,
        "clean_sheet_ev": clean,
        "defcon_ev": defcon,
        "bonus_ev": max(0.0, bonus_ev),
        "save_ev": max(0.0, save_ev),
        "deduction_ev": 0.0,
    }
    result["total_fixture_xpts"] = sum(result.values())
    return result


def next_gameweek_fixture_projections(
    con: sqlite3.Connection,
    season: str,
    team_id: int | None,
    position: str,
    expected_minutes: float,
    probability_of_60_value: float,
    xg90: float,
    xa90: float,
    cbit90: float,
    cbirt90: float,
    bonus_ev: float,
    save_ev: float,
    horizon: int = 6,
    start_gw: int | None = None,
) -> list[dict[str, object]]:
    if team_id is None:
        return [{"gameweek": gw, "fixtures": [], "total_xpts": 0.0} for gw in range(1, horizon + 1)]
    start = current_gameweek(con, season) if start_gw is None else start_gw
    strengths = team_strengths(con, season, start)
    own = strengths.get(team_id, {"attack": 1.0, "defensive_weakness": 1.0})
    rows = con.execute(
        """
        SELECT fixture_id, gameweek, team_h, team_a, team_h_difficulty, team_a_difficulty
        FROM fixtures
        WHERE season = ?
          AND gameweek IS NOT NULL
          AND gameweek > ?
          AND gameweek <= ?
          AND (team_h = ? OR team_a = ?)
        ORDER BY gameweek, fixture_id
        """,
        (season, start, start + horizon, team_id, team_id),
    ).fetchall()
    by_gw = {gw: {"gameweek": gw, "fixtures": [], "total_xpts": 0.0} for gw in range(start + 1, start + horizon + 1)}
    for row in rows:
        opponent_id = row["team_a"] if row["team_h"] == team_id else row["team_h"]
        opponent = strengths.get(opponent_id)
        if opponent:
            attack_factor = max(0.84, min(1.16, own.get("attack", 1.0) * opponent["defensive_weakness"]))
            expected_goals_against = max(0.6, min(2.4, 1.35 * opponent["attack"] * own.get("defensive_weakness", 1.0)))
        else:
            difficulty = row["team_h_difficulty"] if row["team_h"] == team_id else row["team_a_difficulty"]
            attack_factor = max(0.84, min(1.16, 1 + (3 - difficulty) * 0.08))
            expected_goals_against = max(0.6, min(2.4, 1.35 * (1 + (difficulty - 3) * 0.12)))
        projection = project_fixture_xpts(position, expected_minutes, probability_of_60_value, xg90, xa90, cbit90, cbirt90, bonus_ev, save_ev, attack_factor, expected_goals_against)
        item = {
            "fixture_id": row["fixture_id"],
            "opponent_team_id": opponent_id,
            "is_home": row["team_h"] == team_id,
            "attack_factor": round(attack_factor, 3),
            "expected_goals_against": round(expected_goals_against, 3),
            **{key: round(value, 2) for key, value in projection.items()},
        }
        by_gw[row["gameweek"]]["fixtures"].append(item)
        by_gw[row["gameweek"]]["total_xpts"] = round(float(by_gw[row["gameweek"]]["total_xpts"]) + projection["total_fixture_xpts"], 2)
    return list(by_gw.values())
