from __future__ import annotations

import sqlite3

import pandas as pd

from backend.models.config import ModelConfig, prior_weight_for_gw
from backend.models.price_par import ParPoint, build_historical_curves, interpolate


POSITION_TYPES = {"GK": 1, "DEF": 2, "MID": 3, "FWD": 4}


def load_par_points(con: sqlite3.Connection, season: str) -> list[ParPoint]:
    rows = con.execute(
        """
        SELECT position, price, market_mean, value_par, sample_size, confidence
        FROM price_par_points
        WHERE season = ?
        """,
        (season,),
    ).fetchall()
    return [ParPoint(row["position"], row["price"], row["market_mean"], row["value_par"], row["sample_size"], row["confidence"]) for row in rows]


def current_curve_points(con: sqlite3.Connection, season: str, through_gw: int, min_minutes: int = 450) -> list[ParPoint]:
    rows = con.execute(
        """
        SELECT p.position, COALESCE(MAX(g.value), p.current_price) AS price,
               SUM(g.total_points) AS total_points, SUM(g.minutes) AS minutes
        FROM players p
        JOIN player_gameweeks g ON g.season = p.season AND g.player_id = p.player_id
        WHERE p.season = ? AND g.gameweek <= ?
        GROUP BY p.player_id, p.position
        HAVING SUM(g.minutes) >= ?
        """,
        (season, through_gw, min_minutes),
    ).fetchall()
    if not rows:
        return []
    frame = pd.DataFrame(
        [
            {
                "element_type": POSITION_TYPES[row["position"]],
                "now_cost": round(row["price"] * 10),
                "total_points": row["total_points"] * 38 / through_gw,
                "minutes": row["minutes"] * 38 / through_gw,
            }
            for row in rows
        ]
    )
    return build_historical_curves(frame, ModelConfig(historical_min_minutes=min_minutes))


def blended_par_for(
    con: sqlite3.Connection,
    position: str,
    price: float,
    par_season: str,
    current_season: str | None = None,
    as_of_gw: int | None = None,
    current_points: list[ParPoint] | None = None,
) -> tuple[float, float, str]:
    historical = load_par_points(con, par_season)
    historical_mean, historical_par, historical_confidence = interpolate(historical, position, price)
    if current_season is None or as_of_gw is None:
        return historical_mean, historical_par, historical_confidence
    current = current_points if current_points is not None else current_curve_points(con, current_season, as_of_gw)
    if not current:
        return historical_mean, historical_par, historical_confidence
    current_mean, current_par, current_confidence = interpolate(current, position, price)
    historical_weight, current_weight = prior_weight_for_gw(as_of_gw)
    confidence = "LOW" if "LOW" in {historical_confidence, current_confidence} else "MEDIUM"
    return (
        round(historical_mean * historical_weight + current_mean * current_weight, 3),
        round(historical_par * historical_weight + current_par * current_weight, 3),
        confidence,
    )
