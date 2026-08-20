from __future__ import annotations

import sqlite3


def save_rates(con: sqlite3.Connection, season: str, through_gw: int | None = None) -> dict[int, float]:
    clause = "AND pg.gameweek <= ?" if through_gw is not None else ""
    params = (season, through_gw) if through_gw is not None else (season,)
    league = con.execute(
        f"""
        SELECT SUM(pg.saves) AS saves, SUM(pg.minutes) AS minutes
        FROM player_gameweeks pg
        JOIN players p ON p.season = pg.season AND p.player_id = pg.player_id
        WHERE pg.season = ? AND p.position = 'GK' {clause}
        """,
        params,
    ).fetchone()
    prior = ((league["saves"] or 0) / league["minutes"] * 90) if (league["minutes"] or 0) > 0 else 3.0
    rows = con.execute(
        f"""
        SELECT pg.player_id, SUM(pg.saves) AS saves, SUM(pg.minutes) AS minutes
        FROM player_gameweeks pg
        JOIN players p ON p.season = pg.season AND p.player_id = pg.player_id
        WHERE pg.season = ? AND p.position = 'GK' {clause}
        GROUP BY pg.player_id
        """,
        params,
    ).fetchall()
    rates = {}
    for row in rows:
        minutes = row["minutes"] or 0
        if minutes <= 0:
            continue
        raw = (row["saves"] or 0) / minutes * 90
        rates[row["player_id"]] = (raw * minutes + prior * 900) / (minutes + 900)
    return rates


def save_xppg(position: str, expected_minutes: float, saves90: float) -> float:
    if position != "GK":
        return 0.0
    return max(0.0, expected_minutes) / 90 * max(0.0, saves90) / 3
