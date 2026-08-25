from __future__ import annotations

import sqlite3

ROLLING_MATCHES = 6
PRIOR_MATCHES = 6
TEAM_STRENGTH_VERSION = "rolling_team_xg_v1"


def shrink_rate(rate: float, matches: int, prior: float, prior_matches: int = PRIOR_MATCHES) -> float:
    return (rate * matches + prior * prior_matches) / (matches + prior_matches) if matches > 0 else prior


def team_strengths(con: sqlite3.Connection, season: str, through_gw: int | None = None) -> dict[int, dict[str, float]]:
    clause = "AND gameweek <= ?" if through_gw is not None else ""
    params = (season, through_gw) if through_gw is not None else (season,)
    rows = con.execute(
        f"""
        SELECT team_id, gameweek, xg, xga
        FROM team_underlying_gameweeks
        WHERE season = ? {clause}
        """,
        params,
    ).fetchall()
    if not rows:
        return {}
    latest_gw = max(row["gameweek"] for row in rows)
    window_start = max(1, latest_gw - ROLLING_MATCHES + 1)
    rolling = [row for row in rows if row["gameweek"] >= window_start]
    avg_xg = sum(row["xg"] or 0 for row in rolling) / len(rolling)
    avg_xga = sum(row["xga"] or 0 for row in rolling) / len(rolling)
    if not avg_xg or not avg_xga:
        return {}
    by_team: dict[int, list[sqlite3.Row]] = {}
    for row in rolling:
        by_team.setdefault(row["team_id"], []).append(row)
    strengths = {}
    for team_id, team_rows in by_team.items():
        matches = len(team_rows)
        xg = sum(row["xg"] or 0 for row in team_rows) / matches
        xga = sum(row["xga"] or 0 for row in team_rows) / matches
        strengths[team_id] = {
            "attack": max(0.75, min(1.25, shrink_rate(xg, matches, avg_xg) / avg_xg)),
            "defensive_weakness": max(0.75, min(1.25, shrink_rate(xga, matches, avg_xga) / avg_xga)),
        }
    return strengths
