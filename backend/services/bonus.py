from __future__ import annotations

import sqlite3


def bonus_rates(con: sqlite3.Connection, season: str, through_gw: int | None = None) -> dict[int, float]:
    clause = "AND pg.gameweek <= ?" if through_gw is not None else ""
    params = (season, through_gw) if through_gw is not None else (season,)
    position_rows = con.execute(
        f"""
        SELECT p.position, SUM(pg.bonus) AS bonus, SUM(pg.minutes) AS minutes
        FROM player_gameweeks pg
        JOIN players p ON p.season = pg.season AND p.player_id = pg.player_id
        WHERE pg.season = ? {clause}
        GROUP BY p.position
        """,
        params,
    ).fetchall()
    position_mean = {
        row["position"]: (row["bonus"] or 0) / row["minutes"] * 90
        for row in position_rows
        if (row["minutes"] or 0) > 0
    }
    rows = con.execute(
        f"""
        SELECT pg.player_id, p.position, SUM(pg.bonus) AS bonus, SUM(pg.minutes) AS minutes
        FROM player_gameweeks pg
        JOIN players p ON p.season = pg.season AND p.player_id = pg.player_id
        WHERE pg.season = ? {clause}
        GROUP BY pg.player_id, p.position
        """,
        params,
    ).fetchall()
    rates = {}
    for row in rows:
        minutes = row["minutes"] or 0
        if minutes <= 0:
            continue
        raw = (row["bonus"] or 0) / minutes * 90
        prior = position_mean.get(row["position"], 0.0)
        rates[row["player_id"]] = (raw * minutes + prior * 900) / (minutes + 900)
    return rates


def bonus_xppg(expected_minutes: float, bonus90: float) -> float:
    return max(0.0, expected_minutes) / 90 * max(0.0, bonus90)
