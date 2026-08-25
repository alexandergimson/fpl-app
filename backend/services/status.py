from __future__ import annotations

import sqlite3

from backend.models.config import prior_weight_for_gw
from backend.services.ingestion_runs import latest_health_events, latest_ingestion_runs


SOURCES = {
    "players": "Players",
    "fixtures": "Fixtures",
    "price_par_points": "Price Par",
    "player_gameweeks": "Gameweeks",
    "player_underlying_gameweeks": "Player xG/xA",
    "game_underlying_xpts": "Underlying xPts",
    "team_underlying_gameweeks": "Team xG/xGA",
    "price_history": "Prices",
}


def data_status(con: sqlite3.Connection, season: str) -> dict:
    current_gw = con.execute(
        "SELECT value FROM app_state WHERE season = ? AND key = 'current_gameweek'",
        (season,),
    ).fetchone()
    sources = [
        dict(row) | {"key": table, "label": label}
        for table, label in SOURCES.items()
        for row in [
            con.execute(
                f"SELECT COUNT(*) AS rows, MAX(fetched_at) AS fetched_at, MAX(data_period) AS data_period FROM {table} WHERE season = ?",
                (season,),
            ).fetchone()
        ]
    ]
    by_key = {source["key"]: source for source in sources}
    latest_runs = latest_ingestion_runs(con, season, 5)
    fpl_updated = max(
        (by_key[key]["fetched_at"] for key in ("players", "fixtures", "price_history") if by_key[key]["fetched_at"]),
        default=None,
    )
    advanced_updated = max(
        (by_key[key]["fetched_at"] for key in ("player_underlying_gameweeks", "game_underlying_xpts", "team_underlying_gameweeks") if by_key[key]["fetched_at"]),
        default=None,
    )
    current_gameweek = int(current_gw["value"]) if current_gw else None
    historical_weight, current_weight = prior_weight_for_gw(current_gameweek or 0)
    return {
        "season": season,
        "current_gameweek": current_gameweek,
        "latest_ingestion_runs": latest_runs,
        "latest_health_events": latest_health_events(con, season, 10),
        "health_summary": {
            "fpl_last_updated": fpl_updated,
            "advanced_stats_last_updated": advanced_updated,
            "expected_player_count": 500,
            "received_player_count": by_key["players"]["rows"],
            "expected_fixture_count": 300,
            "processed_fixture_count": by_key["fixtures"]["rows"],
            "player_underlying_rows": by_key["player_underlying_gameweeks"]["rows"],
            "team_underlying_rows": by_key["team_underlying_gameweeks"]["rows"],
            "latest_ingestion_status": latest_runs[0]["status"] if latest_runs else None,
            "historical_prior_weight": historical_weight,
            "current_season_weight": current_weight,
        },
        "sources": sources,
    }
