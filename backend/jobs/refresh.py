from __future__ import annotations

import json

from backend.data.db import connect
from backend.ingestion.context import build_fpl_context
from backend.ingestion.loaders import replace_fixtures, replace_gameweek_deadlines, replace_team_underlying, replace_understat_shots, set_state, snapshot_prices, upsert_fpl_bootstrap_gameweek_observations, upsert_players
from backend.ingestion.providers import OfficialFplProvider, UnderstatProvider
from backend.services.canonical_context import materialize_canonical_context
from backend.services.boards import buy_board, freeze_player_gameweek_pars, materialize_current_market
from backend.services.alerts import generate_tracked_alerts
from backend.services.ingestion_runs import add_health_event, finish_ingestion_run, start_ingestion_run
from backend.services.squad import get_team_id, import_public_squad
from backend.services.tracking import COMPONENT_VERSIONS, MODEL_VERSION, create_model_run, snapshot_tracked


def latest_finished_fixture_gameweek(fixtures) -> int:
    frame = fixtures.frame
    if "event" not in frame:
        return 0
    mask = frame["finished"].fillna(False).astype(bool) if "finished" in frame else False
    if "finished_provisional" in frame:
        mask = mask | frame["finished_provisional"].fillna(False).astype(bool)
    events = frame.loc[mask, "event"].dropna()
    return int(events.max()) if not events.empty else 0


def refresh_all(season: str = "2026-27", par_season: str = "2026-27", db_path: str | None = None) -> dict:
    provider = OfficialFplProvider()
    understat = UnderstatProvider()
    with connect(db_path) if db_path else connect() as con:
        run_id = start_ingestion_run(con, season, "local_refresh", "refresh")
    try:
        dataset = provider.bootstrap(season)
        fixtures = provider.fixtures(season)
        gameweek = max(int(dataset.frame.attrs.get("current_gameweek", 0) or 0), latest_finished_fixture_gameweek(fixtures))
        dataset.frame.attrs["current_gameweek"] = gameweek
        with connect(db_path) if db_path else connect() as con:
            players = upsert_players(con, season, dataset.frame, dataset.source, dataset.fetched_at)
            prices = snapshot_prices(con, season, dataset.frame, dataset.source, dataset.fetched_at)
            observations = upsert_fpl_bootstrap_gameweek_observations(con, season, dataset.frame, dataset.fetched_at)
            fixture_count = replace_fixtures(con, season, fixtures.frame, fixtures.source, fixtures.fetched_at)
            replace_gameweek_deadlines(con, season, dataset.frame.attrs.get("events"), dataset.source, dataset.fetched_at)
            con.execute("DELETE FROM player_underlying_gameweeks WHERE season = ? AND source != 'official_fpl_bootstrap'", (season,))
            con.execute("DELETE FROM game_underlying_xpts WHERE season = ? AND source != 'official_fpl_bootstrap'", (season,))
            try:
                team_underlying = understat.team_underlying(season, dataset.frame.attrs.get("teams"), fixtures.frame)
                team_underlying_count = replace_team_underlying(con, season, team_underlying.frame, team_underlying.source, team_underlying.fetched_at) if not team_underlying.frame.empty else 0
            except Exception as exc:
                team_underlying_count = 0
                add_health_event(con, season, run_id, "WARN", "understat_team_failed", str(exc))
            try:
                shot_data = understat.shots(season)
                shot_quality = replace_understat_shots(con, season, shot_data.frame, shot_data.source, shot_data.fetched_at)
                shot_count = shot_quality["rows"]
                if shot_quality["unmapped_players"]:
                    names = ", ".join(shot_quality["unmapped_names"][:10])
                    add_health_event(con, season, run_id, "WARN", "understat_shot_mapping", f"{shot_quality['mapped_players']} mapped, {shot_quality['unmapped_players']} unmapped: {names}")
            except Exception as exc:
                shot_count = 0
                shot_quality = {"rows": 0, "mapped_players": 0, "unmapped_players": 0, "unmapped_names": []}
                add_health_event(con, season, run_id, "WARN", "understat_shots_failed", str(exc))
            frozen_pars = freeze_player_gameweek_pars(con, season, par_season)
            set_state(con, season, "current_gameweek", str(gameweek))
            team_id = get_team_id(con, season)
            imported_squad = import_public_squad(con, season, team_id, provider)["players"] if team_id else 0
            try:
                if team_id:
                    materialize_canonical_context(con, season, build_fpl_context(team_id, season, provider, understat))
            except Exception as exc:
                add_health_event(con, season, run_id, "WARN", "canonical_context_failed", str(exc))
            materialized = 0
            if con.execute("SELECT 1 FROM price_par_points WHERE season = ? LIMIT 1", (par_season,)).fetchone():
                data_cutoff = con.execute("SELECT MAX(fetched_at) AS fetched_at FROM players WHERE season = ?", (season,)).fetchone()["fetched_at"]
                model_run_id = create_model_run(con, season, gameweek, MODEL_VERSION, json.dumps(COMPONENT_VERSIONS, sort_keys=True), data_cutoff)
                board_rows = buy_board(con, season, par_season, None, 2000)
                materialized = materialize_current_market(con, season, par_season, model_run_id, data_cutoff, board_rows)
            snapshots = snapshot_tracked(con, season, par_season, gameweek)
            alerts = generate_tracked_alerts(con, season)
            if players < 500:
                add_health_event(con, season, run_id, "WARN", "player_count", f"Only {players} players received")
            if fixture_count < 300:
                add_health_event(con, season, run_id, "WARN", "fixture_count", f"Only {fixture_count} fixtures received")
            if con.execute("SELECT COUNT(*) AS n FROM player_underlying_gameweeks WHERE season = ?", (season,)).fetchone()["n"] == 0:
                add_health_event(con, season, run_id, "WARN", "missing_player_underlying", "No player xG/xA rows loaded")
            if con.execute("SELECT COUNT(*) AS n FROM team_underlying_gameweeks WHERE season = ?", (season,)).fetchone()["n"] == 0:
                add_health_event(con, season, run_id, "WARN", "missing_team_underlying", "No team xG/xGA rows loaded")
            summary = f"{players} players, {prices} prices, {fixture_count} fixtures, {observations} player GW observations, {team_underlying_count} team xG/xGA rows, {shot_count} Understat player-match rows ({shot_quality['mapped_players']} mapped/{shot_quality['unmapped_players']} unmapped players), {frozen_pars} frozen Pars, {imported_squad} squad picks, {materialized} current metrics, {snapshots} snapshots, {alerts} alerts"
            finish_ingestion_run(con, run_id, "SUCCESS", summary)
        return {
            "run_id": run_id,
            "status": "SUCCESS",
            "gameweek": gameweek,
            "players": players,
            "prices": prices,
            "fixtures": fixture_count,
            "observations": observations,
            "team_underlying": team_underlying_count,
            "shot_metrics": shot_count,
            "understat_shot_mapping": shot_quality,
            "understat_players": {"fetched": 0, "mapped": 0, "unmapped": 0, "duplicate_candidates": 0, "canonical": 0},
            "frozen_pars": frozen_pars,
            "squad": imported_squad,
            "materialized": materialized,
            "snapshots": snapshots,
            "alerts": alerts,
        }
    except Exception as exc:
        with connect(db_path) if db_path else connect() as con:
            finish_ingestion_run(con, run_id, "FAILED", str(exc))
            add_health_event(con, season, run_id, "ERROR", "refresh_failed", str(exc))
        raise
