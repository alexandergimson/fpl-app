from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from backend.services.boards import buy_board
from backend.services.minutes import override_history
from backend.services.roles import role_history
from backend.models.projections import projection_breakdown


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.replace(tzinfo=None)
        except ValueError:
            return None


def _forecast_for_gameweek(prediction: dict, gameweek: int) -> float | None:
    for row in prediction.get("fixture_projection", []) or []:
        if row.get("gameweek") == gameweek:
            value = row.get("total_xpts")
            return float(value) if value is not None else None
    return None


def recent_gameweeks(con: sqlite3.Connection, season: str, player_id: int, limit: int = 10) -> list[dict]:
    rows = con.execute(
        """
        SELECT gameweek, total_points, minutes, value, goals_scored, assists, clean_sheets, bonus
        FROM player_gameweeks
        WHERE season = ? AND player_id = ?
        ORDER BY gameweek DESC
        LIMIT ?
        """,
        (season, player_id, limit),
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def latest_prediction_snapshot(con: sqlite3.Connection, season: str, player_id: int) -> dict | None:
    row = con.execute(
        """
        SELECT snapshots.prediction_json
        FROM current_prediction_snapshots snapshots
        JOIN model_runs ON model_runs.id = snapshots.model_run_id
        WHERE snapshots.season = ? AND snapshots.player_id = ?
        ORDER BY model_runs.created_at DESC, snapshots.model_run_id DESC
        LIMIT 1
        """,
        (season, player_id),
    ).fetchone()
    return json.loads(row["prediction_json"]) if row else None


def prediction_history(con: sqlite3.Connection, season: str, player_id: int) -> list[dict]:
    rows = con.execute(
        """
        SELECT
          snapshots.model_run_id,
          snapshots.gameweek,
          snapshots.prediction_json,
          snapshots.created_at,
          model_runs.data_cutoff,
          model_runs.model_version
        FROM current_prediction_snapshots snapshots
        JOIN model_runs ON model_runs.id = snapshots.model_run_id
        WHERE snapshots.season = ? AND snapshots.player_id = ?
        ORDER BY snapshots.model_run_id
        """,
        (season, player_id),
    ).fetchall()
    fields = [
        "current_price",
        "actual_ppg",
        "value_par",
        "return_delta",
        "performance_delta",
        "neutral_xppg",
        "next_3_xppg",
        "next_6_xppg",
        "forward_delta",
        "buy_delta_6",
        "expected_minutes",
        "projection_confidence",
        "fixture_factor_6",
        "xg90",
        "xa90",
    ]
    history = []
    for row in rows:
        prediction = json.loads(row["prediction_json"])
        item = {
            "gameweek": row["gameweek"],
            "model_run_id": row["model_run_id"],
            "created_at": row["created_at"],
            "data_cutoff": row["data_cutoff"],
            "model_version": row["model_version"],
        }
        for field in fields:
            item[field] = prediction.get(field)
        item["current_par"] = prediction.get("current_par", prediction.get("value_par"))
        history.append(item)
    return history


def gameweek_history(con: sqlite3.Connection, season: str, player_id: int) -> list[dict]:
    rows = con.execute(
        """
        WITH prices AS (
          SELECT
            season,
            player_id,
            gameweek,
            price,
            price - LAG(price) OVER (PARTITION BY season, player_id ORDER BY gameweek) AS price_change
          FROM (
            SELECT season, player_id, gameweek, MAX(price) AS price
            FROM price_history
            WHERE season = ? AND player_id = ? AND gameweek IS NOT NULL
            GROUP BY season, player_id, gameweek
          )
        ),
        underlying AS (
          SELECT season, player_id, gameweek, SUM(xg) AS xg, SUM(xa) AS xa
          FROM player_underlying_gameweeks
          WHERE season = ? AND player_id = ?
          GROUP BY season, player_id, gameweek
        ),
        xpts AS (
          SELECT season, player_id, gameweek, SUM(game_underlying_xpts) AS game_underlying_xpts
          FROM game_underlying_xpts
          WHERE season = ? AND player_id = ?
          GROUP BY season, player_id, gameweek
        ),
        pars AS (
          SELECT season, player_id, gameweek, MAX(value_par) AS value_par
          FROM frozen_player_gameweek_par
          WHERE season = ? AND player_id = ?
          GROUP BY season, player_id, gameweek
        )
        SELECT
          gw.gameweek,
          SUM(gw.total_points) AS points,
          SUM(gw.minutes) AS minutes,
          COALESCE(MAX(gw.value), prices.price) AS price,
          prices.price_change,
          underlying.xg,
          underlying.xa,
          xpts.game_underlying_xpts,
          pars.value_par AS frozen_par,
          CASE WHEN xpts.game_underlying_xpts IS NULL OR pars.value_par IS NULL
            THEN NULL
            ELSE xpts.game_underlying_xpts - pars.value_par
          END AS performance_vs_par
        FROM player_gameweeks gw
        LEFT JOIN prices ON prices.season = gw.season AND prices.player_id = gw.player_id AND prices.gameweek = gw.gameweek
        LEFT JOIN underlying ON underlying.season = gw.season AND underlying.player_id = gw.player_id AND underlying.gameweek = gw.gameweek
        LEFT JOIN xpts ON xpts.season = gw.season AND xpts.player_id = gw.player_id AND xpts.gameweek = gw.gameweek
        LEFT JOIN pars ON pars.season = gw.season AND pars.player_id = gw.player_id AND pars.gameweek = gw.gameweek
        WHERE gw.season = ? AND gw.player_id = ?
        GROUP BY gw.gameweek
        ORDER BY gw.gameweek
        """,
        (season, player_id, season, player_id, season, player_id, season, player_id, season, player_id),
    ).fetchall()
    return [dict(row) for row in rows]


def player_gameweeks(con: sqlite3.Connection, season: str, player_id: int) -> list[dict]:
    player = con.execute(
        """
        SELECT player_id, web_name, team, team_id, position, current_price
        FROM players
        WHERE season = ? AND player_id = ?
        """,
        (season, player_id),
    ).fetchone()
    latest = latest_prediction_snapshot(con, season, player_id) or {}
    team_id = player["team_id"] if player else latest.get("team_id")
    deadlines = {
        row["gameweek"]: row["deadline"]
        for row in con.execute("SELECT gameweek, deadline FROM gameweek_deadlines WHERE season = ?", (season,))
    }
    actuals = {
        row["gameweek"]: dict(row)
        for row in con.execute(
            """
            SELECT
              gw.gameweek,
              SUM(gw.total_points) AS points,
              SUM(gw.minutes) AS minutes,
              COALESCE(MAX(gw.value), prices.price) AS price,
              GROUP_CONCAT(DISTINCT teams.short_name || ' (' || CASE WHEN gw.was_home THEN 'H' ELSE 'A' END || ')') AS opponent
            FROM player_gameweeks gw
            LEFT JOIN teams ON teams.season = gw.season AND teams.team_id = gw.opponent_team
            LEFT JOIN (
              SELECT season, player_id, gameweek, MAX(price) AS price
              FROM price_history
              WHERE season = ? AND player_id = ? AND gameweek > 0
              GROUP BY season, player_id, gameweek
            ) prices ON prices.season = gw.season AND prices.player_id = gw.player_id AND prices.gameweek = gw.gameweek
            WHERE gw.season = ? AND gw.player_id = ?
            GROUP BY gw.gameweek
            """,
            (season, player_id, season, player_id),
        )
    }
    underlying = {
        row["gameweek"]: dict(row)
        for row in con.execute(
            """
            SELECT gameweek, SUM(xg) AS xg, SUM(xa) AS xa
            FROM player_underlying_gameweeks
            WHERE season = ? AND player_id = ?
            GROUP BY gameweek
            """,
            (season, player_id),
        )
    }
    prices = {
        row["gameweek"]: row["price"]
        for row in con.execute(
            """
            SELECT gameweek, MAX(price) AS price
            FROM price_history
            WHERE season = ? AND player_id = ? AND gameweek IS NOT NULL AND gameweek > 0
            GROUP BY gameweek
            """,
            (season, player_id),
        )
    }
    fixture_opponents = {}
    if team_id:
        for row in con.execute(
            """
            SELECT
              fixtures.gameweek,
              CASE WHEN fixtures.team_h = ? THEN away.short_name ELSE home.short_name END AS opponent,
              CASE WHEN fixtures.team_h = ? THEN 'H' ELSE 'A' END AS home_away
            FROM fixtures
            LEFT JOIN teams home ON home.season = fixtures.season AND home.team_id = fixtures.team_h
            LEFT JOIN teams away ON away.season = fixtures.season AND away.team_id = fixtures.team_a
            WHERE fixtures.season = ? AND (fixtures.team_h = ? OR fixtures.team_a = ?)
            """,
            (team_id, team_id, season, team_id, team_id),
        ):
            label = f"{row['opponent']} ({row['home_away']})" if row["opponent"] else None
            if label:
                fixture_opponents.setdefault(row["gameweek"], []).append(label)
    forecasts: dict[int, dict] = {}
    snapshot_rows = con.execute(
        """
        SELECT
          snapshots.model_run_id,
          snapshots.prediction_json,
          model_runs.created_at,
          model_runs.data_cutoff
        FROM current_prediction_snapshots snapshots
        JOIN model_runs ON model_runs.id = snapshots.model_run_id
        WHERE snapshots.season = ? AND snapshots.player_id = ?
        ORDER BY model_runs.created_at, snapshots.model_run_id
        """,
        (season, player_id),
    ).fetchall()
    for row in snapshot_rows:
        created_at = _parse_time(row["created_at"])
        if created_at is None:
            continue
        prediction = json.loads(row["prediction_json"])
        for gameweek, deadline in deadlines.items():
            deadline_at = _parse_time(deadline)
            if deadline_at is None or created_at > deadline_at:
                continue
            score = _forecast_for_gameweek(prediction, gameweek)
            if score is None:
                continue
            current = forecasts.get(gameweek)
            if current is None or (row["created_at"], row["model_run_id"]) > (current["created_at"], current["model_run_id"]):
                forecasts[gameweek] = {
                    "project_score": score,
                    "model_run_id": row["model_run_id"],
                    "forecast_data_cutoff": row["data_cutoff"],
                    "created_at": row["created_at"],
                }
    gameweeks = sorted(set(actuals) | set(underlying) | set(prices) | set(forecasts) | set(fixture_opponents))
    rows = []
    for gameweek in gameweeks:
        actual = actuals.get(gameweek, {})
        under = underlying.get(gameweek, {})
        forecast = forecasts.get(gameweek, {})
        points = actual.get("points")
        project_score = forecast.get("project_score")
        rows.append(
            {
                "gameweek": gameweek,
                "opponent": actual.get("opponent") or ", ".join(fixture_opponents.get(gameweek, [])) or None,
                "home_away": None,
                "points": points,
                "project_score": project_score,
                "performance": points - project_score if points is not None and project_score is not None else None,
                "xg": under.get("xg"),
                "xa": under.get("xa"),
                "minutes": actual.get("minutes"),
                "price": actual.get("price") if actual.get("price") is not None else prices.get(gameweek),
                "model_run_id": forecast.get("model_run_id"),
                "forecast_data_cutoff": forecast.get("forecast_data_cutoff"),
            }
        )
    return rows


def player_detail(con: sqlite3.Connection, season: str, player_id: int, par_season: str = "2026-27") -> dict | None:
    current = latest_prediction_snapshot(con, season, player_id)
    if current is None:
        rows = buy_board(con, season, par_season, None, 2000)
        current = next((row for row in rows if row["player_id"] == player_id), None)
    if not current:
        return None
    player = {
        "id": player_id,
        "name": current["player"],
        "team": current.get("team"),
        "position": current["position"],
        "current_price": current["current_price"],
    }
    return {
        "player": player,
        "current": current,
        "projection_breakdown": projection_breakdown(current),
        "gameweeks": player_gameweeks(con, season, player_id),
        "gameweek_history": gameweek_history(con, season, player_id),
        "prediction_history": prediction_history(con, season, player_id),
        "recent_gameweeks": recent_gameweeks(con, season, player_id),
        "minutes_history": override_history(con, season, player_id),
        "role_history": role_history(con, season, player_id),
    }
