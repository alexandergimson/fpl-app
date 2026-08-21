from __future__ import annotations

import sqlite3


def start_ingestion_run(con: sqlite3.Connection, season: str, provider: str, kind: str) -> int:
    cursor = con.execute(
        """
        INSERT INTO data_ingestion_runs (season, provider, kind, status)
        VALUES (?, ?, ?, 'RUNNING')
        """,
        (season, provider, kind),
    )
    con.commit()
    return int(cursor.lastrowid)


def finish_ingestion_run(con: sqlite3.Connection, run_id: int, status: str, summary: str) -> None:
    con.execute(
        """
        UPDATE data_ingestion_runs
        SET status = ?, summary = ?, finished_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, summary, run_id),
    )
    con.commit()


def add_health_event(con: sqlite3.Connection, season: str, run_id: int | None, level: str, kind: str, message: str) -> None:
    con.execute(
        """
        INSERT INTO data_health_events (season, run_id, level, kind, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (season, run_id, level, kind, message),
    )
    con.commit()


def latest_ingestion_runs(con: sqlite3.Connection, season: str, limit: int = 10) -> list[dict]:
    rows = con.execute(
        """
        SELECT *
        FROM data_ingestion_runs
        WHERE season = ?
        ORDER BY started_at DESC, id DESC
        LIMIT ?
        """,
        (season, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def latest_health_events(con: sqlite3.Connection, season: str, limit: int = 20) -> list[dict]:
    rows = con.execute(
        """
        SELECT *
        FROM data_health_events
        WHERE season = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (season, limit),
    ).fetchall()
    return [dict(row) for row in rows]
