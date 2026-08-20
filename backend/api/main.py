from pathlib import Path

try:
    from fastapi import FastAPI
except ImportError:  # pragma: no cover
    FastAPI = None

from backend.data.db import connect
from backend.services.alerts import acknowledge_alert, generate_tracked_alerts, list_alerts
from backend.services.boards import breakout_board, buy_board, trap_board
from backend.services.player_detail import player_detail
from backend.services.squad import remove_squad_player, squad_analysis, upsert_squad_player
from backend.services.tracking import snapshot_tracked, track_player, tracked_players, tracked_snapshots, untrack_player


if FastAPI:
    app = FastAPI(title="FPL Analytics")

    @app.get("/health")
    def health():
        return {"ok": True}

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
else:
    app = None


def require_fastapi() -> None:
    if FastAPI is None:
        raise SystemExit("FastAPI is not installed. Run `make setup` first.")
