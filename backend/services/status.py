from __future__ import annotations

import sqlite3

from backend.services.ingestion_runs import latest_health_events, latest_ingestion_runs


SOURCES = {
    "players": "Players",
    "fixtures": "Fixtures",
    "price_par_points": "Price Par",
    "player_gameweeks": "Gameweeks",
    "player_underlying_gameweeks": "Player xG/xA",
    "team_underlying_gameweeks": "Team xG/xGA",
    "price_history": "Prices",
}


def data_status(con: sqlite3.Connection, season: str) -> dict:
    current_gw = con.execute(
        "SELECT value FROM app_state WHERE season = ? AND key = 'current_gameweek'",
        (season,),
    ).fetchone()
    return {
        "season": season,
        "current_gameweek": int(current_gw["value"]) if current_gw else None,
        "latest_ingestion_runs": latest_ingestion_runs(con, season, 5),
        "latest_health_events": latest_health_events(con, season, 10),
        "sources": [
            dict(row) | {"key": table, "label": label}
            for table, label in SOURCES.items()
            for row in [
                con.execute(
                    f"SELECT COUNT(*) AS rows, MAX(fetched_at) AS fetched_at, MAX(data_period) AS data_period FROM {table} WHERE season = ?",
                    (season,),
                ).fetchone()
            ]
        ],
    }
