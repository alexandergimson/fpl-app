from __future__ import annotations

import sqlite3

from backend.services.boards import buy_board
from backend.services.fixtures import current_gameweek


def track_player(con: sqlite3.Connection, season: str, player_id: int, note: str | None = None) -> None:
    con.execute(
        """
        INSERT OR REPLACE INTO tracked_players (season, player_id, note)
        VALUES (?, ?, ?)
        """,
        (season, player_id, note),
    )
    con.commit()


def untrack_player(con: sqlite3.Connection, season: str, player_id: int) -> None:
    con.execute("DELETE FROM tracked_players WHERE season = ? AND player_id = ?", (season, player_id))
    con.commit()


def tracked_players(con: sqlite3.Connection, season: str, par_season: str = "2026-27") -> list[dict]:
    tracked = con.execute("SELECT player_id, note, tracked_at FROM tracked_players WHERE season = ?", (season,)).fetchall()
    rows = {row["player_id"]: row for row in buy_board(con, season, par_season, None, 2000)}
    result = []
    for row in tracked:
        board_row = rows.get(row["player_id"])
        if board_row:
            result.append(board_row | {"note": row["note"], "tracked_at": row["tracked_at"]})
    return sorted(result, key=lambda row: row["buy_delta_6"], reverse=True)


def snapshot_tracked(con: sqlite3.Connection, season: str, par_season: str = "2026-27", gameweek: int | None = None) -> int:
    gw = gameweek if gameweek is not None else current_gameweek(con, season)
    rows = tracked_players(con, season, par_season)
    con.executemany(
        """
        INSERT OR IGNORE INTO tracked_snapshots (
          season, player_id, gameweek, price, market_mean, value_par,
          actual_ppg, neutral_xppg, next_3_xppg, next_6_xppg, buy_delta,
          ownership, start_probability, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                season,
                row["player_id"],
                gw,
                row["current_price"],
                row["market_mean"],
                row["value_par"],
                row["actual_ppg"],
                row["neutral_xppg"],
                row["next_3_xppg"],
                row["next_6_xppg"],
                row["buy_delta_6"],
                row["ownership"],
                row["start_probability"],
                row["status"],
            )
            for row in rows
        ],
    )
    con.commit()
    return con.execute(
        "SELECT COUNT(*) AS n FROM tracked_snapshots WHERE season = ? AND gameweek = ?",
        (season, gw),
    ).fetchone()["n"]


def tracked_snapshots(con: sqlite3.Connection, season: str, player_id: int) -> list[dict]:
    rows = con.execute(
        """
        SELECT *
        FROM tracked_snapshots
        WHERE season = ? AND player_id = ?
        ORDER BY gameweek
        """,
        (season, player_id),
    ).fetchall()
    return [dict(row) for row in rows]
