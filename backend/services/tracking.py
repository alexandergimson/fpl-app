from __future__ import annotations

import json
import sqlite3

from backend.services.boards import buy_board
from backend.services.fixtures import current_gameweek

MODEL_VERSION = "v1"
COMPONENT_VERSIONS = {
    "data": "fpl_canonical_v1",
    "minutes": "minutes_baseline_v1",
    "par": "par_iso_v1",
    "projection": "component_projection_v1",
    "role": "role_overrides_v1",
    "team_strength": "fixture_difficulty_v1",
    "underlying": "regressed_underlying_xpts_v1",
}


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
    momentum = tracked_momentum(con, season)
    result = []
    for row in tracked:
        board_row = rows.get(row["player_id"])
        if board_row:
            result.append(board_row | {"note": row["note"], "tracked_at": row["tracked_at"]} | momentum.get(row["player_id"], {}))
    return sorted(result, key=lambda row: row["buy_delta_6"], reverse=True)


def snapshot_tracked(con: sqlite3.Connection, season: str, par_season: str = "2026-27", gameweek: int | None = None) -> int:
    gw = gameweek if gameweek is not None else current_gameweek(con, season)
    if not con.execute("SELECT 1 FROM tracked_players WHERE season = ? LIMIT 1", (season,)).fetchone():
        return 0
    rows = tracked_players(con, season, par_season)
    con.executemany(
        """
        INSERT OR IGNORE INTO tracked_snapshots (
          season, player_id, gameweek, price, market_mean, value_par,
          value_balance, return_delta, performance_delta,
          actual_ppg, neutral_xppg, next_3_xppg, next_6_xppg, buy_delta,
          ownership, start_probability, expected_minutes, projection_confidence,
          fixture_factor_6, xg90, xa90, model_version, component_versions, data_cutoff, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                season,
                row["player_id"],
                gw,
                row["current_price"],
                row["market_mean"],
                row["value_par"],
                row["value_balance"],
                row["return_delta"],
                row["performance_delta"],
                row["actual_ppg"] or 0.0,
                row["neutral_xppg"],
                row["next_3_xppg"],
                row["next_6_xppg"],
                row["buy_delta_6"],
                row["ownership"],
                row["start_probability"],
                row["expected_minutes"],
                row["projection_confidence"],
                row["fixture_factor_6"],
                row["xg90"],
                row["xa90"],
                MODEL_VERSION,
                json.dumps(COMPONENT_VERSIONS, sort_keys=True),
                con.execute("SELECT MAX(fetched_at) AS fetched_at FROM players WHERE season = ?", (season,)).fetchone()["fetched_at"],
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


def tracked_momentum(con: sqlite3.Connection, season: str) -> dict[int, dict]:
    rows = con.execute(
        """
        SELECT player_id, gameweek, buy_delta, status
        FROM tracked_snapshots
        WHERE season = ?
        ORDER BY player_id, gameweek DESC
        """,
        (season,),
    ).fetchall()
    by_player: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        by_player.setdefault(row["player_id"], []).append(row)
    result = {}
    for player_id, snapshots in by_player.items():
        current = snapshots[0]
        previous = snapshots[1] if len(snapshots) > 1 else None
        delta = 0.0 if previous is None else current["buy_delta"] - previous["buy_delta"]
        result[player_id] = {
            "delta_momentum": round(delta, 2),
            "tracking_status": tracking_status(current["buy_delta"], delta),
        }
    return result


def tracking_status(buy_delta: float, delta_momentum: float) -> str:
    if buy_delta >= 0.75 and delta_momentum >= 0:
        return "IMPROVING"
    if buy_delta >= 0.35:
        return "BUY"
    if delta_momentum <= -0.35:
        return "DECLINING"
    if abs(delta_momentum) < 0.1 and buy_delta >= 0:
        return "FULLY PRICED"
    return "WATCH"
