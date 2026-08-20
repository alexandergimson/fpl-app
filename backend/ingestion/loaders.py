from __future__ import annotations

import sqlite3

import pandas as pd

from backend.models.config import POSITIONS
from backend.models.price_par import ParPoint


def upsert_players(con: sqlite3.Connection, season: str, players: pd.DataFrame, source: str, fetched_at: str) -> int:
    rows = []
    for row in players.itertuples(index=False):
        data = row._asdict()
        position = POSITIONS.get(data.get("element_type"), str(data.get("element_type")))
        rows.append(
            (
                season,
                int(data["id"]),
                int(data["code"]) if pd.notna(data.get("code")) else None,
                str(data.get("web_name") or ""),
                str(data.get("first_name") or ""),
                str(data.get("second_name") or ""),
                int(data["team"]) if pd.notna(data.get("team")) else None,
                str(data.get("team_code") or data.get("team") or ""),
                position,
                float(data["now_cost"]) / 10,
                int(data.get("total_points") or 0),
                int(data.get("minutes") or 0),
                float(data["selected_by_percent"]) if pd.notna(data.get("selected_by_percent")) else None,
                str(data.get("status") or ""),
                source,
                fetched_at,
                season,
            )
        )
    con.executemany(
        """
        INSERT OR REPLACE INTO players (
          season, player_id, code, web_name, first_name, second_name, team_id, team,
          position, current_price, total_points, minutes, ownership, status,
          source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()
    return len(rows)


def replace_price_par(
    con: sqlite3.Connection,
    season: str,
    source_season: str,
    points: list[ParPoint],
    min_minutes: int,
    source: str,
    fetched_at: str,
) -> int:
    con.execute("DELETE FROM price_par_points WHERE season = ? AND source_season = ?", (season, source_season))
    con.executemany(
        """
        INSERT INTO price_par_points (
          season, source_season, position, price, market_mean, value_par,
          sample_size, min_minutes, confidence, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                season,
                source_season,
                p.position,
                p.price,
                p.market_mean,
                p.value_par,
                p.sample_size,
                min_minutes,
                p.confidence,
                source,
                fetched_at,
                source_season,
            )
            for p in points
        ],
    )
    con.commit()
    return len(points)
