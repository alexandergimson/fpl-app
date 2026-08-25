from __future__ import annotations

import sqlite3


def player_totals_as_of(con: sqlite3.Connection, season: str, through_gw: int) -> dict[int, dict[str, float]]:
    rows = con.execute(
        """
        SELECT player_id, SUM(total_points) AS total_points, SUM(minutes) AS minutes, MAX(value) AS current_price
        FROM player_gameweeks
        WHERE season = ? AND gameweek <= ?
        GROUP BY player_id
        """,
        (season, through_gw),
    ).fetchall()
    return {
        row["player_id"]: {
            "total_points": row["total_points"] or 0,
            "minutes": row["minutes"] or 0,
            "current_price": row["current_price"],
        }
        for row in rows
    }


def future_points(con: sqlite3.Connection, season: str, player_id: int, start_gw: int, end_gw: int) -> int:
    row = con.execute(
        """
        SELECT SUM(total_points) AS points
        FROM player_gameweeks
        WHERE season = ? AND player_id = ? AND gameweek BETWEEN ? AND ?
        """,
        (season, player_id, start_gw, end_gw),
    ).fetchone()
    return int(row["points"] or 0)


def future_frozen_par(con: sqlite3.Connection, season: str, player_id: int, start_gw: int, end_gw: int) -> float | None:
    row = con.execute(
        """
        SELECT COUNT(*) AS gameweeks, SUM(value_par) AS par
        FROM (
          SELECT gameweek, MAX(value_par) AS value_par
          FROM frozen_player_gameweek_par
          WHERE season = ? AND player_id = ? AND gameweek BETWEEN ? AND ?
          GROUP BY gameweek
        )
        """,
        (season, player_id, start_gw, end_gw),
    ).fetchone()
    expected = end_gw - start_gw + 1
    return float(row["par"]) if row["gameweeks"] == expected else None
