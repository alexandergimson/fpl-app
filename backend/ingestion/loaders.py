from __future__ import annotations

import sqlite3
import html
import re
import unicodedata

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
    con.execute("DELETE FROM player_underlying_gameweeks WHERE season = ? AND source = ?", (season, source))
    rows = []
    underlying = []
    for row in gameweeks.itertuples(index=False):
        data = row._asdict()
        xg = float(data["expected_goals"]) if pd.notna(data.get("expected_goals")) else 0.0
        xa = float(data["expected_assists"]) if pd.notna(data.get("expected_assists")) else 0.0
        player_id = int(data["element"])
        gameweek = int(data["round"])
        minutes = int(data.get("minutes") or 0)
        rows.append(
            (
                season,
                player_id,
                gameweek,
                int(data["fixture"]) if pd.notna(data.get("fixture")) else None,
                int(data["opponent_team"]) if pd.notna(data.get("opponent_team")) else None,
                1 if data.get("was_home") else 0,
                int(data.get("total_points") or 0),
                minutes,
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
        if "expected_goals" in data and "expected_assists" in data and (minutes > 0 or xg > 0 or xa > 0):
            underlying.append((season, player_id, gameweek, minutes, xg, xa, 1, 1, source, fetched_at, season))
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
    con.executemany(
        """
        INSERT OR REPLACE INTO player_underlying_gameweeks (
          season, player_id, gameweek, minutes, xg, xa, xg_observed, xa_observed, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        underlying,
    )
    con.commit()
    if underlying:
        rebuild_game_underlying_xpts(con, season, source)
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
        has_xg = pd.notna(data.get("xg"))
        has_xa = pd.notna(data.get("xa"))
        has_cbit = pd.notna(data.get("cbit"))
        has_cbirt = pd.notna(data.get("cbirt"))
        rows.append(
            (
                season,
                int(data["player_id"]),
                int(data["gameweek"]),
                int(data.get("minutes") or 0),
                float(data["xg"]) if has_xg else 0.0,
                float(data["xa"]) if has_xa else 0.0,
                1 if has_xg else 0,
                1 if has_xa else 0,
                int(data["shots"]) if pd.notna(data.get("shots")) else None,
                int(data["shots_in_box"]) if pd.notna(data.get("shots_in_box")) else None,
                int(data["big_chances"]) if pd.notna(data.get("big_chances")) else None,
                float(data["cbit"]) if has_cbit else None,
                float(data["cbirt"]) if has_cbirt else None,
                1 if has_cbit else 0,
                1 if has_cbirt else 0,
                source,
                fetched_at,
                season,
            )
        )
    con.executemany(
        """
        INSERT OR REPLACE INTO player_underlying_gameweeks (
          season, player_id, gameweek, minutes, xg, xa, xg_observed, xa_observed,
          shots, shots_in_box, big_chances, cbit, cbirt, cbit_observed, cbirt_observed,
          source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()
    rebuild_game_underlying_xpts(con, season, source)
    return len(rows)


def replace_fpl_player_underlying(con: sqlite3.Connection, season: str, players: pd.DataFrame, fetched_at: str) -> int:
    return upsert_fpl_bootstrap_gameweek_observations(con, season, players, fetched_at)


def normalise_name(value: str) -> str:
    folded = unicodedata.normalize("NFKD", html.unescape(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


def replace_understat_player_underlying(con: sqlite3.Connection, season: str, metrics: pd.DataFrame, source: str, fetched_at: str) -> dict[str, int]:
    provider = "understat"
    fpl_rows = con.execute(
        """
        SELECT p.player_id, p.web_name, p.first_name, p.second_name, p.team, t.name AS team_name
        FROM players p
        LEFT JOIN teams t ON t.season = p.season AND t.team_id = p.team_id
        WHERE p.season = ?
        """,
        (season,),
    ).fetchall()
    exact = {}
    by_team = {}
    for row in fpl_rows:
        first_last = f"{str(row['first_name'] or '').split(' ')[0]} {str(row['second_name'] or '').split(' ')[-1]}".strip()
        for team_key in {row["team"], row["team_name"]}:
            if not team_key:
                continue
            for name in {row["web_name"], f"{row['first_name'] or ''} {row['second_name'] or ''}".strip(), first_last}:
                exact[(normalise_name(name), team_key)] = row["player_id"]
                by_team.setdefault(team_key, []).append((normalise_name(name), row["player_id"]))
    raw_rows = []
    cumulative_rows = []
    gameweek_sources = set()
    mapped = unresolved = duplicates = 0
    for row in metrics.itertuples(index=False):
        data = row._asdict()
        external_id = str(data["provider_player_id"])
        team = str(data.get("team") or "")
        name = str(data.get("player_name") or "")
        norm = normalise_name(name)
        player_id = exact.get((norm, team))
        method = "exact_name_team" if player_id else "unresolved"
        confidence = 1.0 if player_id else 0.0
        if not player_id:
            candidates = [candidate_id for candidate_name, candidate_id in by_team.get(team, []) if norm and (norm in candidate_name or candidate_name in norm)]
            if len(set(candidates)) == 1:
                player_id = candidates[0]
                method = "fuzzy_name_team"
                confidence = 0.85
            elif candidates:
                duplicates += 1
        mapped += 1 if player_id else 0
        unresolved += 0 if player_id else 1
        gameweek = int(data["gameweek"]) if pd.notna(data.get("gameweek")) else 0
        minutes = int(data.get("minutes") or 0)
        xg = float(data.get("xg") or 0)
        xa = float(data.get("xa") or 0)
        shots = int(data.get("shots") or 0)
        key_passes = int(data.get("key_passes") or 0)
        previous = con.execute(
            """
            SELECT season_cumulative_minutes, season_cumulative_xg, season_cumulative_xa,
                   season_cumulative_shots, season_cumulative_key_passes
            FROM understat_player_cumulative_observations
            WHERE provider = ? AND season = ? AND external_player_id = ? AND as_of_gameweek < ?
            ORDER BY as_of_gameweek DESC
            LIMIT 1
            """,
            (provider, season, external_id, gameweek),
        ).fetchone()
        gw_minutes = minutes - (previous["season_cumulative_minutes"] if previous else 0)
        gw_xg = xg - (previous["season_cumulative_xg"] if previous else 0.0)
        gw_xa = xa - (previous["season_cumulative_xa"] if previous else 0.0)
        gw_shots = shots - (previous["season_cumulative_shots"] if previous else 0)
        gw_key_passes = key_passes - (previous["season_cumulative_key_passes"] if previous else 0)
        if min(gw_minutes, gw_xg, gw_xa, gw_shots, gw_key_passes) < -0.0001:
            gw_minutes, gw_xg, gw_xa, gw_shots, gw_key_passes = minutes, xg, xa, shots, key_passes
        gw_minutes = max(0, int(gw_minutes))
        gw_xg = max(0.0, gw_xg)
        gw_xa = max(0.0, gw_xa)
        gw_shots = max(0, int(gw_shots))
        gw_key_passes = max(0, int(gw_key_passes))
        raw_rows.append((provider, season, external_id, name, team, gameweek, str(data.get("match_date") or ""), gw_minutes, round(gw_xg, 4), round(gw_xa, 4), gw_shots, gw_key_passes, data.get("position"), player_id, source, fetched_at, season))
        cumulative_rows.append((provider, season, external_id, name, team, gameweek, minutes, xg, xa, shots, key_passes, player_id, source, fetched_at, season))
        con.execute(
            """
            INSERT OR REPLACE INTO external_player_mappings (
              provider, season, external_player_id, external_player_name, external_team,
              fpl_player_id, mapping_method, confidence, verified_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (provider, season, external_id, name, team, player_id, method, confidence, fetched_at),
        )
        if gameweek:
            gameweek_sources.add(gameweek)
    for gameweek in gameweek_sources:
        con.execute("DELETE FROM external_player_underlying_observations WHERE provider = ? AND season = ? AND gameweek = ?", (provider, season, gameweek))
        con.execute("DELETE FROM understat_player_gameweek_observations WHERE provider = ? AND season = ? AND gameweek = ?", (provider, season, gameweek))
    con.executemany(
        """
        INSERT OR REPLACE INTO understat_player_cumulative_observations (
          provider, season, external_player_id, external_player_name, external_team,
          as_of_gameweek, season_cumulative_minutes, season_cumulative_xg,
          season_cumulative_xa, season_cumulative_shots, season_cumulative_key_passes,
          mapped_player_id, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        cumulative_rows,
    )
    con.executemany(
        """
        INSERT OR REPLACE INTO understat_player_gameweek_observations (
          provider, season, external_player_id, external_player_name, external_team,
          gameweek, match_date, gameweek_minutes, gameweek_xg, gameweek_xa,
          gameweek_shots, gameweek_key_passes, position, mapped_player_id,
          source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        raw_rows,
    )
    con.executemany(
        """
        INSERT OR REPLACE INTO external_player_underlying_observations (
          provider, season, external_player_id, external_player_name, external_team,
          gameweek, match_date, minutes, xg, xa, shots, key_passes, position,
          mapped_player_id, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        raw_rows,
    )
    con.commit()
    return {"fetched": len(raw_rows), "mapped": mapped, "unmapped": unresolved, "duplicate_candidates": duplicates, "canonical": 0}


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
        bps = int(data.get("bps") or 0)
        cumulative.append((season, player_id, gameweek, points, minutes, bps, xg, xa, ownership, price, source, fetched_at, season))
        prev = previous.get(player_id)
        gw_points = points - (prev["total_points"] if prev else 0)
        gw_minutes = minutes - (prev["minutes"] if prev else 0)
        gw_bps = bps - (prev["bps"] if prev else 0)
        gw_xg = xg - (prev["xg"] if prev else 0.0)
        gw_xa = xa - (prev["xa"] if prev else 0.0)
        if "starts" in data and pd.notna(data.get("starts")):
            previous_counts = con.execute(
                "SELECT SUM(starts) AS starts, SUM(saves) AS saves, SUM(bonus) AS bonus FROM player_gameweeks WHERE season = ? AND source = ? AND player_id = ? AND gameweek < ?",
                (season, source, player_id, gameweek),
            ).fetchone()
            gw_starts = max(0, int(data.get("starts") or 0) - (previous_counts["starts"] or 0))
            gw_saves = max(0, int(data.get("saves") or 0) - (previous_counts["saves"] or 0))
            gw_bonus = max(0, int(data.get("bonus") or 0) - (previous_counts["bonus"] or 0))
        else:
            gw_starts = 0
            gw_saves = 0
        gw_bonus = 0
        if gw_points < 0 or gw_minutes < 0 or gw_bps < 0 or gw_xg < -0.0001 or gw_xa < -0.0001:
            continue
        if not any((gw_points, gw_minutes, gw_starts, gw_saves, gw_bonus, gw_bps)) and abs(gw_xg) < 0.0001 and abs(gw_xa) < 0.0001:
            continue
        gameweeks.append((season, player_id, gameweek, 0, None, 0, gw_points, gw_minutes, gw_starts, 0, 0, 0, 0, gw_saves, gw_bonus, gw_bps, None, None, None, price, source, fetched_at, season))
        if gw_minutes > 0 or gw_xg > 0 or gw_xa > 0:
            underlying.append((season, player_id, gameweek, gw_minutes, round(gw_xg, 4), round(gw_xa, 4), 1, 1, source, fetched_at, season))
    con.executemany(
        """
        INSERT OR REPLACE INTO player_cumulative_observations (
          season, player_id, gameweek, total_points, minutes, bps, xg, xa,
          ownership, current_price, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        cumulative,
    )
    con.execute("DELETE FROM player_gameweeks WHERE season = ? AND source = ? AND gameweek = ?", (season, source, gameweek))
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
          season, player_id, gameweek, minutes, xg, xa, xg_observed, xa_observed, source, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
