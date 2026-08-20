from pathlib import Path

try:
    from fastapi import FastAPI
except ImportError:  # pragma: no cover
    FastAPI = None

from backend.data.db import connect
from backend.services.boards import buy_board


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
else:
    app = None


def require_fastapi() -> None:
    if FastAPI is None:
        raise SystemExit("FastAPI is not installed. Run `make setup` first.")
