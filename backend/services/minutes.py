from __future__ import annotations

import sqlite3

from backend.models.projections import expected_minutes


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
