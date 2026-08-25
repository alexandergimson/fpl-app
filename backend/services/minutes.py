from __future__ import annotations

import sqlite3

from backend.models.projections import expected_minutes, probability_of_60

MINUTES_MODEL_VERSION = "minutes_hurdle_v1"


def add_minutes_override(
    con: sqlite3.Connection,
    season: str,
    player_id: int,
    start_probability: float,
    expected_minutes_if_starting: float,
    substitute_probability: float,
    expected_minutes_if_sub: float,
    reason: str,
) -> None:
    con.execute(
        """
        INSERT INTO minutes_overrides (
          season, player_id, start_probability, expected_minutes_if_starting,
          substitute_probability, expected_minutes_if_sub, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            season,
            player_id,
            start_probability,
            expected_minutes_if_starting,
            substitute_probability,
            expected_minutes_if_sub,
            reason,
        ),
    )
    con.commit()


def latest_minutes_overrides(con: sqlite3.Connection, season: str) -> dict[int, dict]:
    rows = con.execute(
        """
        SELECT *
        FROM minutes_overrides
        WHERE season = ?
        ORDER BY player_id, created_at DESC, id DESC
        """,
        (season,),
    ).fetchall()
    result = {}
    for row in rows:
        if row["player_id"] not in result:
            result[row["player_id"]] = dict(row) | {
                "expected_minutes": expected_minutes(
                    row["start_probability"],
                    row["expected_minutes_if_starting"],
                    row["substitute_probability"],
                    row["expected_minutes_if_sub"],
                )
            }
    return result


def baseline_minutes_profiles(con: sqlite3.Connection, season: str, denominator: int, through_gw: int | None = None) -> dict[int, dict]:
    clause = "AND gameweek <= ?" if through_gw is not None else ""
    params = (season, through_gw) if through_gw is not None else (season,)
    rows = con.execute(
        f"""
        SELECT player_id,
               SUM(minutes) AS minutes,
               SUM(starts) AS starts,
               SUM(CASE WHEN starts = 1 THEN minutes ELSE 0 END) AS start_minutes,
               SUM(CASE WHEN starts = 0 AND minutes > 0 THEN 1 ELSE 0 END) AS sub_appearances,
               SUM(CASE WHEN starts = 0 AND minutes > 0 THEN minutes ELSE 0 END) AS sub_minutes
        FROM player_gameweeks
        WHERE season = ? {clause}
        GROUP BY player_id
        """,
        params,
    ).fetchall()
    profiles = {}
    for row in rows:
        starts = row["starts"] or 0
        subs = row["sub_appearances"] or 0
        start_probability = starts / max(1, denominator)
        substitute_probability = subs / max(1, denominator)
        start_minutes = (row["start_minutes"] or 0) / starts if starts else 0.0
        sub_minutes = (row["sub_minutes"] or 0) / subs if subs else 0.0
        profiles[row["player_id"]] = minutes_profile(start_probability, start_minutes, substitute_probability, sub_minutes)
    return profiles


def fallback_minutes_profile(minutes: int, denominator: int) -> dict:
    average = minutes / max(1, denominator)
    return minutes_profile(min(1.0, average / 60), min(90.0, max(0.0, average)), 0.0, 0.0)


def minutes_profile(start_probability: float, start_minutes: float, substitute_probability: float, sub_minutes: float) -> dict:
    start_probability = max(0.0, min(1.0, start_probability))
    substitute_probability = max(0.0, min(1.0 - start_probability, substitute_probability))
    start_minutes = max(0.0, min(90.0, start_minutes))
    sub_minutes = max(0.0, min(90.0, sub_minutes))
    return {
        "start_probability": start_probability,
        "expected_minutes_if_starting": start_minutes,
        "substitute_probability": substitute_probability,
        "expected_minutes_if_sub": sub_minutes,
        "expected_minutes": expected_minutes(start_probability, start_minutes, substitute_probability, sub_minutes),
        "probability_of_60": probability_of_60(start_probability, start_minutes),
    }


def override_history(con: sqlite3.Connection, season: str, player_id: int) -> list[dict]:
    rows = con.execute(
        """
        SELECT *
        FROM minutes_overrides
        WHERE season = ? AND player_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (season, player_id),
    ).fetchall()
    return [dict(row) for row in rows]
