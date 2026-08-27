from pathlib import Path

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:  # pragma: no cover
    FastAPI = None

from backend.data.db import connect
from backend.ingestion.providers import OfficialFplProvider
from backend.services.alerts import acknowledge_alert, generate_tracked_alerts, list_alerts
from backend.services.boards import breakout_board, buy_board, paginated_players, player_forward_lineage, player_performance_lineage, trap_board
from backend.services.canonical_context import manager_context
from backend.services.minutes import add_minutes_override, override_history
from backend.services.player_detail import player_detail
from backend.services.prices import price_movements
from backend.services.roles import add_role_override, role_history
from backend.services.squad import get_team_id, import_public_squad, remove_squad_player, squad_analysis, upsert_squad_player
from backend.services.status import data_status
from backend.services.tracking import snapshot_tracked, track_player, tracked_players, tracked_snapshots, untrack_player


if FastAPI:
    app = FastAPI(title="FPL Analytics")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/data-status")
    def get_data_status(season: str = "2026-27"):
        with connect() as con:
            return data_status(con, season)

    @app.get("/price-par")
    def price_par(season: str = "2026-27"):
        with connect() as con:
            rows = con.execute(
                """
                SELECT position, price, market_mean, value_par, sample_size, confidence
                FROM price_par_points
                WHERE season = ?
                ORDER BY position, price
                """,
                (season,),
            ).fetchall()
        return [dict(row) for row in rows]

    @app.get("/price-movements")
    def get_price_movements(season: str = "2026-27", limit: int = 25):
        with connect() as con:
            return price_movements(con, season, limit)

    @app.get("/players")
    def players(season: str = "2025-26", limit: int = 100):
        with connect() as con:
            rows = con.execute(
                """
                SELECT player_id, web_name, team, position, current_price, total_points, minutes, ownership, status
                FROM players
                WHERE season = ?
                ORDER BY total_points DESC
                LIMIT ?
                """,
                (season, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    @app.get("/players/{player_id}/performance-lineage")
    def get_player_performance_lineage(player_id: int, season: str = "2026-27", par_season: str = "2026-27"):
        with connect() as con:
            return player_performance_lineage(con, season, player_id, par_season)

    @app.get("/players/{player_id}/forward-lineage")
    def get_player_forward_lineage(player_id: int, season: str = "2026-27", par_season: str = "2026-27"):
        with connect() as con:
            return player_forward_lineage(con, season, player_id, par_season)

    @app.get("/players/{player_id}")
    def get_player(player_id: int, season: str = "2026-27", par_season: str = "2026-27"):
        with connect() as con:
            detail = player_detail(con, season, player_id, par_season)
        return detail or {}

    @app.get("/buy-board")
    def get_buy_board(
        season: str = "2026-27",
        par_season: str = "2026-27",
        gameweeks_played: int | None = None,
        limit: int = 50,
        as_of_gw: int | None = None,
    ):
        with connect() as con:
            return buy_board(con, season, par_season, gameweeks_played, limit, as_of_gw)

    @app.get("/all-players")
    def get_all_players(
        season: str = "2026-27",
        par_season: str = "2026-27",
        gameweeks_played: int | None = None,
        limit: int = 2000,
        as_of_gw: int | None = None,
        page: int = 1,
        page_size: int = 15,
        position: str = "ALL",
        min_price: float | None = None,
        max_price: float | None = None,
        tracked: bool = False,
        confidence: str = "ALL",
        sort: str = "forward_delta",
        direction: str = "desc",
        search: str = "",
        quick_filter: str = "ALL",
    ):
        with connect() as con:
            if limit != 2000:
                return buy_board(con, season, par_season, gameweeks_played, limit, as_of_gw)
            return paginated_players(con, season, par_season, gameweeks_played, page, page_size, position, min_price, max_price, tracked, confidence, sort, direction, search, quick_filter)

    @app.get("/breakout-board")
    def get_breakout_board(
        season: str = "2026-27",
        par_season: str = "2026-27",
        gameweeks_played: int | None = None,
        limit: int = 50,
        as_of_gw: int | None = None,
    ):
        with connect() as con:
            return breakout_board(con, season, par_season, gameweeks_played, limit, as_of_gw)

    @app.get("/trap-board")
    def get_trap_board(
        season: str = "2026-27",
        par_season: str = "2026-27",
        gameweeks_played: int | None = None,
        limit: int = 50,
        as_of_gw: int | None = None,
    ):
        with connect() as con:
            return trap_board(con, season, par_season, gameweeks_played, limit, as_of_gw)

    @app.get("/tracked-players")
    def get_tracked_players(season: str = "2026-27", par_season: str = "2026-27"):
        with connect() as con:
            return tracked_players(con, season, par_season)

    @app.post("/tracked-players/{player_id}")
    def post_tracked_player(player_id: int, season: str = "2026-27", note: str | None = None):
        with connect() as con:
            track_player(con, season, player_id, note)
        return {"ok": True}

    @app.delete("/tracked-players/{player_id}")
    def delete_tracked_player(player_id: int, season: str = "2026-27"):
        with connect() as con:
            untrack_player(con, season, player_id)
        return {"ok": True}

    @app.post("/tracked-snapshots")
    def post_tracked_snapshots(season: str = "2026-27", par_season: str = "2026-27", gameweek: int | None = None):
        with connect() as con:
            count = snapshot_tracked(con, season, par_season, gameweek)
        return {"snapshots": count}

    @app.get("/tracked-players/{player_id}/snapshots")
    def get_tracked_snapshots(player_id: int, season: str = "2026-27"):
        with connect() as con:
            return tracked_snapshots(con, season, player_id)

    @app.get("/squad")
    def get_squad(season: str = "2026-27", par_season: str = "2026-27", bank: float = 0.0):
        with connect() as con:
            return squad_analysis(con, season, par_season, bank)

    @app.get("/settings")
    def get_settings(season: str = "2026-27"):
        with connect() as con:
            return {"fpl_team_id": get_team_id(con, season), "manager": manager_context(con, season)}

    @app.post("/settings/fpl-team")
    def post_fpl_team(team_id: int, season: str = "2026-27"):
        provider = OfficialFplProvider()
        with connect() as con:
            return import_public_squad(con, season, team_id, provider)

    @app.post("/squad/{player_id}")
    def post_squad_player(player_id: int, purchase_price: float, season: str = "2026-27", current_price: float | None = None):
        with connect() as con:
            upsert_squad_player(con, season, player_id, purchase_price, current_price)
        return {"ok": True}

    @app.delete("/squad/{player_id}")
    def delete_squad_player(player_id: int, season: str = "2026-27"):
        with connect() as con:
            remove_squad_player(con, season, player_id)
        return {"ok": True}

    @app.get("/alerts")
    def get_alerts(season: str = "2026-27", include_acknowledged: bool = False):
        with connect() as con:
            return list_alerts(con, season, include_acknowledged)

    @app.post("/alerts/generate")
    def post_generate_alerts(season: str = "2026-27"):
        with connect() as con:
            count = generate_tracked_alerts(con, season)
        return {"alerts": count}

    @app.post("/alerts/{alert_id}/ack")
    def post_acknowledge_alert(alert_id: int):
        with connect() as con:
            acknowledge_alert(con, alert_id)
        return {"ok": True}

    @app.post("/minutes-overrides/{player_id}")
    def post_minutes_override(
        player_id: int,
        start_probability: float,
        expected_minutes_if_starting: float,
        substitute_probability: float,
        expected_minutes_if_sub: float,
        reason: str,
        season: str = "2026-27",
    ):
        with connect() as con:
            add_minutes_override(
                con,
                season,
                player_id,
                start_probability,
                expected_minutes_if_starting,
                substitute_probability,
                expected_minutes_if_sub,
                reason,
            )
        return {"ok": True}

    @app.get("/minutes-overrides/{player_id}")
    def get_minutes_overrides(player_id: int, season: str = "2026-27"):
        with connect() as con:
            return override_history(con, season, player_id)

    @app.post("/role-overrides/{player_id}")
    def post_role_override(
        player_id: int,
        penalties: float = 0,
        direct_free_kicks: float = 0,
        corners: float = 0,
        indirect_free_kicks: float = 0,
        reason: str = "",
        season: str = "2026-27",
    ):
        with connect() as con:
            add_role_override(con, season, player_id, penalties, direct_free_kicks, corners, indirect_free_kicks, reason)
        return {"ok": True}

    @app.get("/role-overrides/{player_id}")
    def get_role_overrides(player_id: int, season: str = "2026-27"):
        with connect() as con:
            return role_history(con, season, player_id)
else:
    app = None


def require_fastapi() -> None:
    if FastAPI is None:
        raise SystemExit("FastAPI is not installed. Run `make setup` first.")
