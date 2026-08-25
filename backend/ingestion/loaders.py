from __future__ import annotations

import sqlite3

import pandas as pd

from backend.models.config import POSITIONS
from backend.models.price_par import ParPoint
from backend.services.underlying import rebuild_game_underlying_xpts


def upsert_players(con: sqlite3.Connection, season: str, players: pd.DataFrame, source: str, fetched_at: str) -> int:
    teams = players.attrs.get("teams")
    team_names = {}
    if teams is not None and not teams.empty:
        team_names = dict(zip(teams["id"], teams["short_name"]))
        con.executemany(
            """
            INSERT OR REPLACE INTO teams (season, team_id, name, short_name, source, fetched_at, data_period)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (season, int(row.id), str(row.name), str(row.short_name), source, fetched_at, season)
                for row in teams.itertuples(index=False)
            ],
        )
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
                str(team_names.get(data.get("team")) or data.get("team_code") or data.get("team") or ""),
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


def snapshot_prices(con: sqlite3.Connection, season: str, players: pd.DataFrame, source: str, fetched_at: str) -> int:
    gameweek = players.attrs.get("current_gameweek")
    rows = []
    for row in players.itertuples(index=False):
        data = row._asdict()
        rows.append(
            (
                season,
                int(data["id"]),
                int(gameweek) if gameweek is not None else None,
                fetched_at,
                float(data["now_cost"]) / 10,
                source,
                fetched_at,
                season,
            )
        )
    con.executemany(
        """
        INSERT OR REPLACE INTO price_history (
          season, player_id, gameweek, observed_on, price, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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


def replace_fixtures(con: sqlite3.Connection, season: str, fixtures: pd.DataFrame, source: str, fetched_at: str) -> int:
    con.execute("DELETE FROM fixtures WHERE season = ?", (season,))
    rows = []
    for row in fixtures.itertuples(index=False):
        data = row._asdict()
        rows.append(
            (
                season,
                int(data["id"]),
                int(data["event"]) if pd.notna(data.get("event")) else None,
                str(data.get("kickoff_time") or ""),
                int(data["team_h"]),
                int(data["team_a"]),
                int(data["team_h_difficulty"]),
                int(data["team_a_difficulty"]),
                1 if data.get("finished") or data.get("finished_provisional") else 0,
                source,
                fetched_at,
                season,
            )
        )
    con.executemany(
        """
        INSERT INTO fixtures (
          season, fixture_id, gameweek, kickoff_time, team_h, team_a,
          team_h_difficulty, team_a_difficulty, finished, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()
    return len(rows)


def set_state(con: sqlite3.Connection, season: str, key: str, value: str) -> None:
    con.execute(
        """
        INSERT OR REPLACE INTO app_state (season, key, value, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (season, key, value),
    )
    con.commit()


def replace_player_gameweeks(con: sqlite3.Connection, season: str, gameweeks: pd.DataFrame, source: str, fetched_at: str) -> int:
    con.execute("DELETE FROM player_gameweeks WHERE season = ?", (season,))
    rows = []
    for row in gameweeks.itertuples(index=False):
        data = row._asdict()
        rows.append(
            (
                season,
                int(data["element"]),
                int(data["round"]),
                int(data["fixture"]) if pd.notna(data.get("fixture")) else None,
                int(data["opponent_team"]) if pd.notna(data.get("opponent_team")) else None,
                1 if data.get("was_home") else 0,
                int(data.get("total_points") or 0),
                int(data.get("minutes") or 0),
                int(data.get("starts") or 0),
                int(data.get("goals_scored") or 0),
                int(data.get("assists") or 0),
                int(data.get("clean_sheets") or 0),
                int(data.get("goals_conceded") or 0),
                int(data.get("saves") or 0),
                int(data.get("bonus") or 0),
                int(data.get("bps") or 0),
                int(data["selected"]) if pd.notna(data.get("selected")) else None,
                int(data["transfers_in"]) if pd.notna(data.get("transfers_in")) else None,
                int(data["transfers_out"]) if pd.notna(data.get("transfers_out")) else None,
                float(data["value"]) / 10 if pd.notna(data.get("value")) else None,
                source,
                fetched_at,
                season,
            )
        )
    con.executemany(
        """
        INSERT OR REPLACE INTO player_gameweeks (
          season, player_id, gameweek, fixture_id, opponent_team, was_home,
          total_points, minutes, starts, goals_scored, assists, clean_sheets,
          goals_conceded, saves, bonus, bps, selected, transfers_in, transfers_out,
          value, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()
    return len(rows)


def replace_player_underlying(con: sqlite3.Connection, season: str, metrics: pd.DataFrame, source: str, fetched_at: str) -> int:
    required = {"player_id", "gameweek", "minutes", "xg", "xa"}
    missing = required - set(metrics.columns)
    if missing:
        raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
    con.execute("DELETE FROM player_underlying_gameweeks WHERE season = ? AND source = ?", (season, source))
    rows = []
    for row in metrics.itertuples(index=False):
        data = row._asdict()
        rows.append(
            (
                season,
                int(data["player_id"]),
                int(data["gameweek"]),
                int(data.get("minutes") or 0),
                float(data.get("xg") or 0),
                float(data.get("xa") or 0),
                int(data["shots"]) if pd.notna(data.get("shots")) else None,
                int(data["shots_in_box"]) if pd.notna(data.get("shots_in_box")) else None,
                int(data["big_chances"]) if pd.notna(data.get("big_chances")) else None,
                float(data["cbit"]) if pd.notna(data.get("cbit")) else None,
                float(data["cbirt"]) if pd.notna(data.get("cbirt")) else None,
                source,
                fetched_at,
                season,
            )
        )
    con.executemany(
        """
        INSERT OR REPLACE INTO player_underlying_gameweeks (
          season, player_id, gameweek, minutes, xg, xa, shots, shots_in_box,
          big_chances, cbit, cbirt, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()
    rebuild_game_underlying_xpts(con, season, source)
    return len(rows)


def replace_fpl_player_underlying(con: sqlite3.Connection, season: str, players: pd.DataFrame, fetched_at: str) -> int:
    return upsert_fpl_bootstrap_gameweek_observations(con, season, players, fetched_at)


def upsert_fpl_bootstrap_gameweek_observations(con: sqlite3.Connection, season: str, players: pd.DataFrame, fetched_at: str) -> int:
    gameweek = int(players.attrs.get("current_gameweek") or 0)
    if gameweek <= 0:
        return 0
    source = "official_fpl_bootstrap"
    cumulative = []
    gameweeks = []
    underlying = []
    previous = {
        row["player_id"]: row
        for row in con.execute(
            """
            SELECT c.*
            FROM player_cumulative_observations c
            JOIN (
              SELECT player_id, MAX(gameweek) AS gameweek
              FROM player_cumulative_observations
              WHERE season = ? AND source = ? AND gameweek < ?
              GROUP BY player_id
            ) latest ON latest.player_id = c.player_id AND latest.gameweek = c.gameweek
            WHERE c.season = ? AND c.source = ?
            """,
            (season, source, gameweek, season, source),
        )
    }
    for row in players.itertuples(index=False):
        data = row._asdict()
        player_id = int(data["id"])
        points = int(data.get("total_points") or 0)
        minutes = int(data.get("minutes") or 0)
        xg = float(data.get("expected_goals") or 0)
        xa = float(data.get("expected_assists") or 0)
        ownership = float(data["selected_by_percent"]) if pd.notna(data.get("selected_by_percent")) else None
        price = float(data["now_cost"]) / 10 if pd.notna(data.get("now_cost")) else None
        cumulative.append((season, player_id, gameweek, points, minutes, xg, xa, ownership, price, source, fetched_at, season))
        prev = previous.get(player_id)
        gw_points = points - (prev["total_points"] if prev else 0)
        gw_minutes = minutes - (prev["minutes"] if prev else 0)
        gw_xg = xg - (prev["xg"] if prev else 0.0)
        gw_xa = xa - (prev["xa"] if prev else 0.0)
        if gw_points < 0 or gw_minutes < 0 or gw_xg < -0.0001 or gw_xa < -0.0001:
            continue
        gameweeks.append((season, player_id, gameweek, 0, None, 0, gw_points, gw_minutes, 1 if gw_minutes >= 60 else 0, 0, 0, 0, 0, 0, 0, 0, None, None, None, price, source, fetched_at, season))
        if gw_minutes > 0 or gw_xg > 0 or gw_xa > 0:
            underlying.append((season, player_id, gameweek, gw_minutes, round(gw_xg, 4), round(gw_xa, 4), source, fetched_at, season))
    con.executemany(
        """
        INSERT OR REPLACE INTO player_cumulative_observations (
          season, player_id, gameweek, total_points, minutes, xg, xa,
          ownership, current_price, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        cumulative,
    )
    con.executemany(
        """
        INSERT OR REPLACE INTO player_gameweeks (
          season, player_id, gameweek, fixture_id, opponent_team, was_home,
          total_points, minutes, starts, goals_scored, assists, clean_sheets,
          goals_conceded, saves, bonus, bps, selected, transfers_in, transfers_out,
          value, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        gameweeks,
    )
    con.execute("DELETE FROM player_underlying_gameweeks WHERE season = ? AND source = ? AND gameweek = ?", (season, source, gameweek))
    con.executemany(
        """
        INSERT OR REPLACE INTO player_underlying_gameweeks (
          season, player_id, gameweek, minutes, xg, xa, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        underlying,
    )
    con.commit()
    rebuild_game_underlying_xpts(con, season, source)
    return len(gameweeks)


def replace_team_underlying(con: sqlite3.Connection, season: str, metrics: pd.DataFrame, source: str, fetched_at: str) -> int:
    required = {"team_id", "gameweek", "xg", "xga"}
    missing = required - set(metrics.columns)
    if missing:
        raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
    con.execute("DELETE FROM team_underlying_gameweeks WHERE season = ? AND source = ?", (season, source))
    rows = []
    for row in metrics.itertuples(index=False):
        data = row._asdict()
        rows.append(
            (
                season,
                int(data["team_id"]),
                int(data["gameweek"]),
                None if "is_home" not in data or pd.isna(data.get("is_home")) else int(bool(data["is_home"])),
                float(data.get("xg") or 0),
                float(data.get("xga") or 0),
                source,
                fetched_at,
                season,
            )
        )
    con.executemany(
        """
        INSERT OR REPLACE INTO team_underlying_gameweeks (
          season, team_id, gameweek, is_home, xg, xga, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()
    return len(rows)
