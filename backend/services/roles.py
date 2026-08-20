from __future__ import annotations

import sqlite3


ROLE_KEYS = ("penalties", "direct_free_kicks", "corners", "indirect_free_kicks")


def add_role_override(
    con: sqlite3.Connection,
    season: str,
    player_id: int,
    penalties: float,
    direct_free_kicks: float,
    corners: float,
    indirect_free_kicks: float,
    reason: str,
) -> None:
    con.execute(
        """
        INSERT INTO player_role_overrides (
          season, player_id, penalties, direct_free_kicks, corners, indirect_free_kicks, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (season, player_id, penalties, direct_free_kicks, corners, indirect_free_kicks, reason),
    )
    con.commit()


def latest_role_overrides(con: sqlite3.Connection, season: str) -> dict[int, dict]:
    rows = con.execute(
        """
        SELECT r.*
        FROM player_role_overrides r
        JOIN (
          SELECT player_id, MAX(id) AS id
          FROM player_role_overrides
          WHERE season = ?
          GROUP BY player_id
        ) latest ON latest.id = r.id
        """,
        (season,),
    ).fetchall()
    return {row["player_id"]: dict(row) for row in rows}


def role_history(con: sqlite3.Connection, season: str, player_id: int) -> list[dict]:
    rows = con.execute(
        """
        SELECT penalties, direct_free_kicks, corners, indirect_free_kicks, reason, created_at
        FROM player_role_overrides
        WHERE season = ? AND player_id = ?
        ORDER BY id DESC
        """,
        (season, player_id),
    ).fetchall()
    return [dict(row) for row in rows]
