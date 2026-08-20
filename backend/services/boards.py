from __future__ import annotations

import sqlite3

from backend.models.price_par import ParPoint, interpolate
from backend.services.valuation import player_status


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


def infer_gameweeks(rows, season: str, par_season: str) -> int:
    if season < par_season:
        return 38
    max_points = max((row["total_points"] for row in rows), default=0)
    # ponytail: official bootstrap can look like preseason while still carrying prior full-season totals.
    return 38 if max_points > 50 else 1


def buy_board(con: sqlite3.Connection, season: str, par_season: str = "2026-27", gameweeks_played: int | None = None, limit: int = 50):
    par_points = load_par_points(con, par_season)
    rows = con.execute(
        """
        SELECT player_id, web_name, team, position, current_price, total_points, minutes, ownership, status
        FROM players
        WHERE season = ?
        """,
        (season,),
    ).fetchall()
    denominator = gameweeks_played or infer_gameweeks(rows, season, par_season)
    board = []
    for row in rows:
        market_mean, value_par, par_confidence = interpolate(par_points, row["position"], row["current_price"])
        actual_ppg = row["total_points"] / max(1, denominator)
        minutes_confidence = min(1.0, row["minutes"] / max(1, denominator * 90))
        neutral_xppg = actual_ppg * (0.35 + 0.65 * minutes_confidence) + market_mean * (1 - minutes_confidence) * 0.35
        next_3_xppg = neutral_xppg
        next_6_xppg = neutral_xppg
        buy_delta_3 = next_3_xppg - value_par
        buy_delta_6 = next_6_xppg - value_par
        confidence = min(1.0, 0.45 + minutes_confidence * 0.55)
        board.append(
            {
                "player_id": row["player_id"],
                "player": row["web_name"],
                "team": row["team"],
                "position": row["position"],
                "current_price": row["current_price"],
                "market_mean": round(market_mean, 2),
                "value_par": round(value_par, 2),
                "actual_ppg": round(actual_ppg, 2),
                "neutral_xppg": round(neutral_xppg, 2),
                "next_3_xppg": round(next_3_xppg, 2),
                "next_6_xppg": round(next_6_xppg, 2),
                "buy_delta_3": round(buy_delta_3, 2),
                "buy_delta_6": round(buy_delta_6, 2),
                "expected_minutes": round(row["minutes"] / max(1, denominator), 1),
                "start_probability": round(min(1.0, row["minutes"] / max(1, denominator * 60)), 2),
                "minutes_confidence": "HIGH" if minutes_confidence >= 0.75 else "MEDIUM" if minutes_confidence >= 0.5 else "LOW",
                "projection_confidence": round(confidence, 2),
                "par_confidence": par_confidence,
                "ownership": row["ownership"],
                "status": player_status(buy_delta_6, buy_delta_3, confidence, actual_ppg - market_mean),
            }
        )
    return sorted(board, key=lambda item: item["buy_delta_6"], reverse=True)[:limit]
