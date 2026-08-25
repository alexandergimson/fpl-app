from __future__ import annotations

import sqlite3

from backend.models.config import prior_weight_for_gw
from backend.services.goalkeepers import observed_save_rates
from backend.services.ingestion_runs import latest_health_events, latest_ingestion_runs
from backend.services.underlying import performance_evidence_state, player_underlying_rates, team_defensive_xga


SOURCES = {
    "players": "Players",
    "fixtures": "Fixtures",
    "price_par_points": "Price Par",
    "player_cumulative_observations": "FPL Cumulative",
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
    performance_rates = player_underlying_rates(con, season)
    team_xga = team_defensive_xga(con, season)
    saves = observed_save_rates(con, season)
    performance_coverage = {"missing": 0, "partial": 0, "sufficient": 0}
    position_coverage = {position: {"missing": 0, "partial": 0, "sufficient": 0} for position in ("GK", "DEF", "MID", "FWD")}
    player_rows = con.execute("SELECT player_id, team_id, position FROM players WHERE season = ?", (season,)).fetchall()
    for player in player_rows:
        state = performance_evidence_state(player["position"], performance_rates.get(player["player_id"]), team_xga.get(player["team_id"]) is not None, player["player_id"] in saves)
        performance_coverage[state] += 1
        position_coverage[player["position"]][state] += 1
    understat_player = con.execute(
        """
        SELECT COUNT(*) AS fetched,
               SUM(CASE WHEN mapped_player_id IS NOT NULL THEN 1 ELSE 0 END) AS mapped,
               MAX(fetched_at) AS fetched_at
        FROM external_player_underlying_observations
        WHERE provider = 'understat' AND season = ?
        """,
        (season,),
    ).fetchone()
    mapping = con.execute(
        """
        SELECT COUNT(*) AS rows,
               SUM(CASE WHEN fpl_player_id IS NOT NULL THEN 1 ELSE 0 END) AS mapped,
               SUM(CASE WHEN mapping_method = 'unresolved' THEN 1 ELSE 0 END) AS unresolved
        FROM external_player_mappings
        WHERE provider = 'understat' AND season = ?
        """,
        (season,),
    ).fetchone()
    prior_counts = {"player_history": 0, "historical_position_price": 0, "historical_position": 0, "none": 0}
    low_confidence_priors = 0
    for rates in performance_rates.values():
        prior_counts[rates.get("prior_source", "none")] = prior_counts.get(rates.get("prior_source", "none"), 0) + 1
        low_confidence_priors += 1 if rates.get("prior_confidence") == "LOW" else 0
    latest_projection = con.execute(
        "SELECT model_version, component_versions, data_cutoff, created_at FROM model_runs WHERE season = ? ORDER BY id DESC LIMIT 1",
        (season,),
    ).fetchone()
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
            "performance_sufficient_players": performance_coverage["sufficient"],
            "performance_partial_players": performance_coverage["partial"],
            "performance_missing_players": performance_coverage["missing"],
            "performance_coverage_by_position": position_coverage,
            "understat_team_rows": by_key["team_underlying_gameweeks"]["rows"],
            "understat_team_mapping_coverage": by_key["team_underlying_gameweeks"]["rows"],
            "understat_player_rows_fetched": understat_player["fetched"] or 0,
            "understat_player_rows_mapped": understat_player["mapped"] or 0,
            "understat_player_last_updated": understat_player["fetched_at"],
            "understat_player_mapping_rows": mapping["rows"] or 0,
            "understat_player_mapping_mapped": mapping["mapped"] or 0,
            "understat_player_mapping_unresolved": mapping["unresolved"] or 0,
            "player_prior_coverage": prior_counts,
            "low_confidence_prior_players": low_confidence_priors,
            "latest_fixture_projection_run": dict(latest_projection) if latest_projection else None,
            "latest_ingestion_status": latest_runs[0]["status"] if latest_runs else None,
            "historical_prior_weight": historical_weight,
            "current_season_weight": current_weight,
        },
        "sources": sources,
    }
