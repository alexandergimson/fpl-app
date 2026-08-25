from __future__ import annotations

from backend.data.db import connect
from backend.ingestion.loaders import replace_fixtures, replace_team_underlying, set_state, snapshot_prices, upsert_fpl_bootstrap_gameweek_observations, upsert_players
from backend.ingestion.providers import OfficialFplProvider, UnderstatProvider
from backend.services.boards import freeze_player_gameweek_pars
from backend.services.alerts import generate_tracked_alerts
from backend.services.ingestion_runs import add_health_event, finish_ingestion_run, start_ingestion_run
from backend.services.squad import get_team_id, import_public_squad
from backend.services.tracking import snapshot_tracked


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
            con.execute("DELETE FROM player_underlying_gameweeks WHERE season = ? AND source != 'official_fpl_bootstrap'", (season,))
            con.execute("DELETE FROM game_underlying_xpts WHERE season = ? AND source != 'official_fpl_bootstrap'", (season,))
            try:
                team_underlying = understat.team_underlying(season, dataset.frame.attrs.get("teams"), fixtures.frame)
                team_underlying_count = replace_team_underlying(con, season, team_underlying.frame, team_underlying.source, team_underlying.fetched_at) if not team_underlying.frame.empty else 0
            except Exception as exc:
                team_underlying_count = 0
                add_health_event(con, season, run_id, "WARN", "understat_team_failed", str(exc))
            frozen_pars = freeze_player_gameweek_pars(con, season, par_season)
            set_state(con, season, "current_gameweek", str(gameweek))
            team_id = get_team_id(con, season)
            imported_squad = import_public_squad(con, season, team_id, provider)["players"] if team_id else 0
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
            summary = f"{players} players, {prices} prices, {fixture_count} fixtures, {observations} player GW observations, {team_underlying_count} team xG/xGA rows, Understat player baseline disabled, {frozen_pars} frozen Pars, {imported_squad} squad picks, {snapshots} snapshots, {alerts} alerts"
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
            "understat_players": {"fetched": 0, "mapped": 0, "unmapped": 0, "duplicate_candidates": 0, "canonical": 0},
            "frozen_pars": frozen_pars,
            "squad": imported_squad,
            "snapshots": snapshots,
            "alerts": alerts,
        }
    except Exception as exc:
        with connect(db_path) if db_path else connect() as con:
            finish_ingestion_run(con, run_id, "FAILED", str(exc))
            add_health_event(con, season, run_id, "ERROR", "refresh_failed", str(exc))
        raise
