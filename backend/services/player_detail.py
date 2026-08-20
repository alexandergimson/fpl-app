from __future__ import annotations

import sqlite3

from backend.services.boards import buy_board
from backend.services.tracking import tracked_snapshots
from backend.models.projections import projection_breakdown


def recent_gameweeks(con: sqlite3.Connection, season: str, player_id: int, limit: int = 10) -> list[dict]:
    rows = con.execute(
        """
        SELECT gameweek, total_points, minutes, value, goals_scored, assists, clean_sheets, bonus
        FROM player_gameweeks
        WHERE season = ? AND player_id = ?
        ORDER BY gameweek DESC
        LIMIT ?
        """,
        (season, player_id, limit),
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def player_detail(con: sqlite3.Connection, season: str, player_id: int, par_season: str = "2026-27") -> dict | None:
    rows = buy_board(con, season, par_season, None, 2000)
    current = next((row for row in rows if row["player_id"] == player_id), None)
    if not current:
        return None
    return {
        "current": current,
        "projection_breakdown": projection_breakdown(current),
        "recent_gameweeks": recent_gameweeks(con, season, player_id),
        "tracked_snapshots": tracked_snapshots(con, season, player_id),
    }
