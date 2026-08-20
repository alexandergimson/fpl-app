from __future__ import annotations

import sqlite3


GOAL_POINTS = {"GK": 6, "DEF": 6, "MID": 5, "FWD": 4}


def player_underlying_rates(con: sqlite3.Connection, season: str, through_gw: int | None = None) -> dict[int, dict[str, float]]:
    clause = "AND gameweek <= ?" if through_gw is not None else ""
    params = (season, through_gw) if through_gw is not None else (season,)
    rows = con.execute(
        f"""
        SELECT player_id, SUM(minutes) AS minutes, SUM(xg) AS xg, SUM(xa) AS xa
        FROM player_underlying_gameweeks
        WHERE season = ? {clause}
        GROUP BY player_id
        """,
        params,
    ).fetchall()
    rates = {}
    for row in rows:
        minutes = row["minutes"] or 0
        if minutes <= 0:
            continue
        rates[row["player_id"]] = {
            "xg90": (row["xg"] or 0) / minutes * 90,
            "xa90": (row["xa"] or 0) / minutes * 90,
            "underlying_minutes": minutes,
        }
    return rates


def attacking_xppg(position: str, expected_minutes: float, xg90: float, xa90: float) -> float:
    minutes_factor = max(0.0, expected_minutes) / 90
    return minutes_factor * (xg90 * GOAL_POINTS.get(position, 4) + xa90 * 3)
