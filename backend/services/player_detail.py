from __future__ import annotations

import json
import sqlite3

from backend.services.boards import buy_board
from backend.services.minutes import override_history
from backend.services.roles import role_history
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


def latest_prediction_snapshot(con: sqlite3.Connection, season: str, player_id: int) -> dict | None:
    row = con.execute(
        """
        SELECT snapshots.prediction_json
        FROM current_prediction_snapshots snapshots
        JOIN model_runs ON model_runs.id = snapshots.model_run_id
        WHERE snapshots.season = ? AND snapshots.player_id = ?
        ORDER BY model_runs.created_at DESC, snapshots.model_run_id DESC
        LIMIT 1
        """,
        (season, player_id),
    ).fetchone()
    return json.loads(row["prediction_json"]) if row else None


def player_detail(con: sqlite3.Connection, season: str, player_id: int, par_season: str = "2026-27") -> dict | None:
    current = latest_prediction_snapshot(con, season, player_id)
    if current is None:
        rows = buy_board(con, season, par_season, None, 2000)
        current = next((row for row in rows if row["player_id"] == player_id), None)
    if not current:
        return None
    return {
        "current": current,
        "projection_breakdown": projection_breakdown(current),
        "recent_gameweeks": recent_gameweeks(con, season, player_id),
        "minutes_history": override_history(con, season, player_id),
        "role_history": role_history(con, season, player_id),
        "tracked_snapshots": tracked_snapshots(con, season, player_id),
    }
