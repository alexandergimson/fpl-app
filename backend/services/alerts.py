from __future__ import annotations

import sqlite3


def list_alerts(con: sqlite3.Connection, season: str, include_acknowledged: bool = False) -> list[dict]:
    clause = "" if include_acknowledged else "AND acknowledged_at IS NULL"
    rows = con.execute(
        f"""
        SELECT id, season, player_id, kind, message, created_at, acknowledged_at
        FROM alerts
        WHERE season = ? {clause}
        ORDER BY created_at DESC, id DESC
        """,
        (season,),
    ).fetchall()
    return [dict(row) for row in rows]


def acknowledge_alert(con: sqlite3.Connection, alert_id: int) -> None:
    con.execute("UPDATE alerts SET acknowledged_at = CURRENT_TIMESTAMP WHERE id = ?", (alert_id,))
    con.commit()


def insert_alert(con: sqlite3.Connection, season: str, player_id: int | None, kind: str, dedupe_key: str, message: str) -> None:
    con.execute(
        """
        INSERT OR IGNORE INTO alerts (season, player_id, kind, dedupe_key, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (season, player_id, kind, dedupe_key, message),
    )


def generate_tracked_alerts(con: sqlite3.Connection, season: str) -> int:
    rows = con.execute(
        """
        SELECT s.*, p.web_name
        FROM tracked_snapshots s
        JOIN players p ON p.season = s.season AND p.player_id = s.player_id
        WHERE s.season = ?
        ORDER BY s.player_id, s.gameweek
        """,
        (season,),
    ).fetchall()
    before = con.total_changes
    by_player: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        by_player.setdefault(row["player_id"], []).append(row)
    for player_id, snapshots in by_player.items():
        if len(snapshots) < 2:
            continue
        previous, current = snapshots[-2], snapshots[-1]
        name = current["web_name"]
        if previous["buy_delta"] < 0 <= current["buy_delta"]:
            insert_alert(
                con,
                season,
                player_id,
                "tracked_crossed_positive",
                f"{season}:{player_id}:{current['gameweek']}:crossed_positive",
                f"{name} moved above Value Par delta.",
            )
        if current["buy_delta"] - previous["buy_delta"] >= 0.4:
            insert_alert(
                con,
                season,
                player_id,
                "tracked_delta_jump",
                f"{season}:{player_id}:{current['gameweek']}:delta_jump",
                f"{name} Buy Delta increased by {current['buy_delta'] - previous['buy_delta']:.2f}.",
            )
        if current["status"] != previous["status"]:
            insert_alert(
                con,
                season,
                player_id,
                "tracked_status_change",
                f"{season}:{player_id}:{current['gameweek']}:status_change:{current['status']}",
                f"{name} changed status from {previous['status']} to {current['status']}.",
            )
    con.commit()
    return con.total_changes - before
