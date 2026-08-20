from __future__ import annotations

import sqlite3


def team_strengths(con: sqlite3.Connection, season: str, through_gw: int | None = None) -> dict[int, dict[str, float]]:
    clause = "AND gameweek <= ?" if through_gw is not None else ""
    params = (season, through_gw) if through_gw is not None else (season,)
    league = con.execute(
        f"""
        SELECT AVG(xg) AS avg_xg, AVG(xga) AS avg_xga
        FROM team_underlying_gameweeks
        WHERE season = ? {clause}
        """,
        params,
    ).fetchone()
    avg_xg = league["avg_xg"] or 0
    avg_xga = league["avg_xga"] or 0
    if not avg_xg or not avg_xga:
        return {}
    rows = con.execute(
        f"""
        SELECT team_id, AVG(xg) AS xg, AVG(xga) AS xga
        FROM team_underlying_gameweeks
        WHERE season = ? {clause}
        GROUP BY team_id
        """,
        params,
    ).fetchall()
    return {
        row["team_id"]: {
            "attack": max(0.75, min(1.25, (row["xg"] or avg_xg) / avg_xg)),
            "defensive_weakness": max(0.75, min(1.25, (row["xga"] or avg_xga) / avg_xga)),
        }
        for row in rows
    }
