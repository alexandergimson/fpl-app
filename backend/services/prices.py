from __future__ import annotations

import sqlite3


def price_movements(con: sqlite3.Connection, season: str, limit: int = 25) -> list[dict]:
    rows = con.execute(
        """
        WITH ranked AS (
          SELECT
            season, player_id, gameweek, observed_on, price,
            ROW_NUMBER() OVER (PARTITION BY season, player_id ORDER BY observed_on ASC) AS first_rank,
            ROW_NUMBER() OVER (PARTITION BY season, player_id ORDER BY observed_on DESC) AS latest_rank
          FROM price_history
          WHERE season = ?
        ),
        first_prices AS (
          SELECT player_id, price AS first_price
          FROM ranked
          WHERE first_rank = 1
        ),
        latest_prices AS (
          SELECT player_id, gameweek, observed_on, price AS latest_price
          FROM ranked
          WHERE latest_rank = 1
        )
        SELECT
          p.player_id, p.web_name AS player, p.team, p.position,
          f.first_price, l.latest_price,
          ROUND(l.latest_price - f.first_price, 1) AS price_change,
          l.gameweek, l.observed_on
        FROM latest_prices l
        JOIN first_prices f ON f.player_id = l.player_id
        JOIN players p ON p.season = ? AND p.player_id = l.player_id
        WHERE l.latest_price != f.first_price
        ORDER BY ABS(l.latest_price - f.first_price) DESC, p.web_name
        LIMIT ?
        """,
        (season, season, limit),
    ).fetchall()
    return [dict(row) for row in rows]
