from __future__ import annotations

import sqlite3

from backend.models.price_par import ParPoint
from backend.models.projections import role_xppg
from backend.services.bonus import bonus_rates, bonus_xppg
from backend.services.fixtures import adjusted_horizon_ppg, clean_sheet_horizon_ev, next_gameweek_fixture_projections, upcoming_expected_opponent_goals, upcoming_fixture_factors
from backend.services.goalkeepers import observed_save_rates, save_rates, save_xppg
from backend.services.history import player_totals_as_of
from backend.services.minutes import baseline_minutes_profiles, fallback_minutes_profile, latest_minutes_overrides, minutes_profile
from backend.services.price_par import blended_par_for, current_curve_points
from backend.services.roles import ROLE_KEYS, latest_role_overrides
from backend.services.underlying import PERFORMANCE_MODEL_VERSION, calculate_regressed_process_components, clean_sheet_process_xppg, performance_confidence, performance_evidence_state, player_underlying_rates, team_defensive_xga
from backend.services.valuation import captain_adjusted_delta, player_status, projection_confidence


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


def team_completed_fixtures(con: sqlite3.Connection, season: str, as_of_gw: int | None = None) -> dict[int, int]:
    clause = "AND gameweek <= ?" if as_of_gw is not None else ""
    params = (season, as_of_gw, season, as_of_gw) if as_of_gw is not None else (season, season)
    rows = con.execute(
        f"""
        SELECT team_id, COUNT(*) AS played
        FROM (
          SELECT DISTINCT team_id, gameweek
          FROM (
            SELECT team_h AS team_id, gameweek FROM fixtures WHERE season = ? AND finished = 1 {clause}
            UNION ALL
            SELECT team_a AS team_id, gameweek FROM fixtures WHERE season = ? AND finished = 1 {clause}
          )
        )
        GROUP BY team_id
        """,
        params,
    ).fetchall()
    return {row["team_id"]: row["played"] for row in rows}


def actual_ppg(points: int, team_id: int | None, completed_by_team: dict[int, int], fallback_denominator: int | None = None) -> float | None:
    played = completed_by_team.get(team_id) if team_id is not None else None
    if played:
        return points / played
    if fallback_denominator:
        return points / fallback_denominator
    return None


def frozen_par_summary(con: sqlite3.Connection, season: str, as_of_gw: int | None = None) -> dict[int, dict[str, float]]:
    clause = "AND gameweek <= ?" if as_of_gw is not None else ""
    params = (season, as_of_gw) if as_of_gw is not None else (season,)
    rows = con.execute(
        f"""
        SELECT player_id, COUNT(*) AS frozen_gameweeks, SUM(value_par) AS frozen_par_total
        FROM (
          SELECT player_id, gameweek, MAX(value_par) AS value_par
          FROM frozen_player_gameweek_par
          WHERE season = ? {clause}
          GROUP BY player_id, gameweek
        )
        GROUP BY player_id
        """,
        params,
    ).fetchall()
    return {row["player_id"]: {"frozen_gameweeks": row["frozen_gameweeks"], "frozen_par_total": row["frozen_par_total"] or 0.0} for row in rows}


def value_balance_and_return_delta(points: int, played: int | None, value_par: float, frozen: dict[str, float] | None = None) -> tuple[float | None, float | None]:
    if not played:
        return None, None
    frozen_count = int(frozen["frozen_gameweeks"]) if frozen and frozen.get("frozen_gameweeks") is not None else 0
    if frozen_count != played:
        return None, None
    frozen_total = float(frozen["frozen_par_total"])
    balance = points - frozen_total
    return balance, balance / played


def freeze_player_gameweek_pars(con: sqlite3.Connection, season: str, par_season: str = "2026-27", model_version: str = "par_iso_v1") -> int:
    if not con.execute("SELECT 1 FROM price_par_points WHERE season = ? LIMIT 1", (par_season,)).fetchone():
        return 0
    rows = con.execute(
        """
        SELECT
          p.player_id, f.gameweek, 0 AS fixture_id,
          COALESCE(MAX(gw.value), MAX(ph.price), p.current_price) AS price,
          p.position,
          COALESCE(MAX(gw.fetched_at), MAX(ph.fetched_at), MAX(f.fetched_at), p.fetched_at) AS fetched_at
        FROM players p
        JOIN (
          SELECT season, gameweek, team_id, MAX(fetched_at) AS fetched_at
          FROM (
            SELECT season, gameweek, team_h AS team_id, fetched_at
            FROM fixtures
            WHERE season = ? AND finished = 1
            UNION ALL
            SELECT season, gameweek, team_a AS team_id, fetched_at
            FROM fixtures
            WHERE season = ? AND finished = 1
          )
          GROUP BY season, gameweek, team_id
        ) f ON f.season = p.season AND f.team_id = p.team_id
        LEFT JOIN player_gameweeks gw
          ON gw.season = p.season
          AND gw.player_id = p.player_id
          AND gw.gameweek = f.gameweek
        LEFT JOIN price_history ph
          ON ph.season = p.season
          AND ph.player_id = p.player_id
          AND ph.gameweek = f.gameweek
        WHERE p.season = ?
        GROUP BY p.player_id, f.gameweek, p.current_price, p.position, p.fetched_at
        """,
        (season, season, season),
    ).fetchall()
    if not rows:
        rows = con.execute(
            """
            SELECT
              p.player_id, gw.gameweek, 0 AS fixture_id,
              COALESCE(MAX(gw.value), p.current_price) AS price,
              p.position,
              COALESCE(MAX(gw.fetched_at), p.fetched_at) AS fetched_at
            FROM player_gameweeks gw
            JOIN players p ON p.season = gw.season AND p.player_id = gw.player_id
            WHERE gw.season = ?
            GROUP BY p.player_id, gw.gameweek, p.current_price, p.position, p.fetched_at
            """,
            (season,),
        ).fetchall()
    inserts = []
    for row in rows:
        _, value_par, _ = blended_par_for(con, row["position"], row["price"], par_season)
        inserts.append(
            (
                season,
                row["player_id"],
                row["gameweek"],
                row["fixture_id"],
                row["price"],
                row["position"],
                round(value_par, 2),
                model_version,
                "price_par_points",
                par_season,
                row["fetched_at"],
            )
        )
    before = con.total_changes
    con.executemany(
        """
        INSERT OR IGNORE INTO frozen_player_gameweek_par (
          season, player_id, gameweek, fixture_id, price, position, value_par,
          par_model_version, source, source_version, data_cutoff
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        inserts,
    )
    inserted = con.total_changes - before
    con.execute(
        """
        DELETE FROM frozen_player_gameweek_par
        WHERE season = ?
          AND fixture_id != 0
          AND EXISTS (
            SELECT 1
            FROM frozen_player_gameweek_par canonical
            WHERE canonical.season = frozen_player_gameweek_par.season
              AND canonical.player_id = frozen_player_gameweek_par.player_id
              AND canonical.gameweek = frozen_player_gameweek_par.gameweek
              AND canonical.fixture_id = 0
          )
        """,
        (season,),
    )
    con.commit()
    return inserted


def buy_board(
    con: sqlite3.Connection,
    season: str,
    par_season: str = "2026-27",
    gameweeks_played: int | None = None,
    limit: int = 50,
    as_of_gw: int | None = None,
):
    rows = con.execute(
        """
        SELECT player_id, web_name, team_id, team, position, current_price, total_points, minutes, ownership, status
        FROM players
        WHERE season = ?
        """,
        (season,),
    ).fetchall()
    as_of_totals = player_totals_as_of(con, season, as_of_gw) if as_of_gw is not None else {}
    underlying = player_underlying_rates(con, season, as_of_gw)
    team_xga = team_defensive_xga(con, season, as_of_gw)
    bonus90_by_player = bonus_rates(con, season, as_of_gw)
    saves90_by_player = save_rates(con, season, as_of_gw)
    observed_saves90_by_player = observed_save_rates(con, season, as_of_gw)
    overrides = latest_minutes_overrides(con, season)
    roles = latest_role_overrides(con, season)
    current_par_points = current_curve_points(con, season, as_of_gw) if as_of_gw is not None else None
    denominator = gameweeks_played or as_of_gw or infer_gameweeks(rows, season, par_season)
    completed_by_team = team_completed_fixtures(con, season, as_of_gw)
    frozen_pars = frozen_par_summary(con, season, as_of_gw)
    baseline_minutes = baseline_minutes_profiles(con, season, denominator, as_of_gw)
    actual_fallback = denominator if season < par_season and not completed_by_team else None
    previous_deltas = {
        row["player_id"]: row["buy_delta"]
        for row in con.execute(
            """
            SELECT s.player_id, s.buy_delta
            FROM tracked_snapshots s
            JOIN (
              SELECT player_id, MAX(gameweek) AS gameweek
              FROM tracked_snapshots
              WHERE season = ?
              GROUP BY player_id
            ) latest ON latest.player_id = s.player_id AND latest.gameweek = s.gameweek
            WHERE s.season = ?
            """,
            (season, season),
        )
    }
    price_trends = {
        row["player_id"]: row["price_trend"]
        for row in con.execute(
            """
            SELECT player_id, MAX(price) - MIN(price) AS price_trend
            FROM price_history
            WHERE season = ?
            GROUP BY player_id
            """,
            (season,),
        )
    }
    board = []
    for row in rows:
        if as_of_gw is not None and row["player_id"] not in as_of_totals:
            continue
        totals = as_of_totals.get(row["player_id"], {})
        price = totals.get("current_price") or row["current_price"]
        points = totals.get("total_points", row["total_points"])
        minutes = totals.get("minutes", row["minutes"])
        market_mean, value_par, par_confidence = blended_par_for(
            con,
            row["position"],
            price,
            par_season,
            season if as_of_gw is not None else None,
            as_of_gw,
            current_par_points,
        )
        actual = actual_ppg(points, row["team_id"], completed_by_team, actual_fallback)
        played = completed_by_team.get(row["team_id"]) if row["team_id"] is not None else actual_fallback
        minute_profile = baseline_minutes.get(row["player_id"]) or fallback_minutes_profile(minutes, denominator)
        minutes_confidence = min(1.0, minute_profile["expected_minutes"] / 60)
        neutral_xppg = market_mean * (0.35 + 0.65 * minutes_confidence)
        expected_minutes = minute_profile["expected_minutes"]
        override = overrides.get(row["player_id"])
        if override:
            minute_profile = minutes_profile(
                override["start_probability"],
                override["expected_minutes_if_starting"],
                override["substitute_probability"],
                override["expected_minutes_if_sub"],
            )
            expected_minutes = minute_profile["expected_minutes"]
            minutes_confidence = max(minutes_confidence, 0.75)
        rates = underlying.get(row["player_id"])
        bonus = bonus_xppg(expected_minutes, bonus90_by_player.get(row["player_id"], 0.0))
        projected_saves = save_xppg(row["position"], expected_minutes, saves90_by_player.get(row["player_id"], 0.0))
        observed_saves = save_xppg(row["position"], expected_minutes, observed_saves90_by_player.get(row["player_id"], 0.0))
        own_xga = team_xga.get(row["team_id"])
        process_clean_sheet = clean_sheet_process_xppg(row["position"], expected_minutes, own_xga, minute_profile["probability_of_60"]) if own_xga is not None else 0.0
        performance_xppg = None
        if rates:
            parts = calculate_regressed_process_components(
                row["position"],
                expected_minutes,
                rates["xg90"],
                rates["xa90"],
                rates["cbit90"],
                rates["cbirt90"],
                own_xga,
                minute_profile["probability_of_60"],
                bonus,
                observed_saves,
            )
            defcon = parts["defcon_ev"]
            performance_xppg = parts["game_underlying_xpts"]
            neutral_xppg = performance_xppg - observed_saves + projected_saves
        else:
            defcon = 0.0
        role = roles.get(row["player_id"])
        role_boost = role_xppg(row["position"], expected_minutes, role)
        performance_data_state = performance_evidence_state(row["position"], rates, own_xga is not None, row["player_id"] in observed_saves90_by_player)
        neutral_xppg += role_boost
        fixture_factors = upcoming_fixture_factors(con, season, row["team_id"], 6)
        opponent_goals = upcoming_expected_opponent_goals(con, season, row["team_id"], 6)
        neutral_clean_sheet = process_clean_sheet if own_xga is not None else clean_sheet_horizon_ev([], row["position"], expected_minutes, 1, minute_profile["probability_of_60"])
        clean_sheet_3 = clean_sheet_horizon_ev(opponent_goals, row["position"], expected_minutes, 3, minute_profile["probability_of_60"])
        clean_sheet_6 = clean_sheet_horizon_ev(opponent_goals, row["position"], expected_minutes, 6, minute_profile["probability_of_60"])
        fixture_projection = []
        if rates:
            fixture_projection = next_gameweek_fixture_projections(
                con,
                season,
                row["team_id"],
                row["position"],
                expected_minutes,
                minute_profile["probability_of_60"],
                rates["xg90"],
                rates["xa90"],
                rates["cbit90"],
                rates["cbirt90"],
                bonus + role_boost,
                projected_saves,
                6,
            )
            gw_points = [float(item["total_xpts"]) for item in fixture_projection]
            next_3_xppg = sum(gw_points[:3]) / 3
            next_6_xppg = sum(gw_points[:6]) / 6
        else:
            open_play_xppg = max(0.0, neutral_xppg - neutral_clean_sheet)
            next_3_xppg = adjusted_horizon_ppg(open_play_xppg, fixture_factors, 3) + clean_sheet_3
            next_6_xppg = adjusted_horizon_ppg(open_play_xppg, fixture_factors, 6) + clean_sheet_6
        buy_delta_3 = next_3_xppg - value_par
        buy_delta_6 = next_6_xppg - value_par
        value_balance, return_delta = value_balance_and_return_delta(points, played, value_par, frozen_pars.get(row["player_id"]))
        performance_delta = performance_xppg - value_par if performance_data_state == "sufficient" and performance_xppg is not None else None
        historical_delta = return_delta
        value_trend = buy_delta_6 - previous_deltas.get(row["player_id"], buy_delta_6)
        captain_delta = captain_adjusted_delta(next_6_xppg, value_par, price)
        confidence = projection_confidence(minutes_confidence, rates["underlying_minutes"] if rates else 0, row["status"], role is not None)
        opportunity_score = buy_delta_6 * minutes_confidence * confidence
        board.append(
            {
                "player_id": row["player_id"],
                "player": row["web_name"],
                "team": row["team"],
                "position": row["position"],
                "current_price": price,
                "market_mean": round(market_mean, 2),
                "value_par": round(value_par, 2),
                "value_balance": round(value_balance, 2) if value_balance is not None else None,
                "actual_ppg": round(actual, 2) if actual is not None else None,
                "neutral_xppg": round(neutral_xppg, 2),
                "underlying_xppg": round(performance_xppg if performance_xppg is not None else neutral_xppg, 2),
                "process_xppg_regressed": round(performance_xppg, 2) if performance_xppg is not None else None,
                "next_3_xppg": round(next_3_xppg, 2),
                "next_6_xppg": round(next_6_xppg, 2),
                "buy_delta_3": round(buy_delta_3, 2),
                "buy_delta_6": round(buy_delta_6, 2),
                "historical_delta": round(historical_delta, 2) if historical_delta is not None else None,
                "return_delta": round(return_delta, 2) if return_delta is not None else None,
                "performance_delta": round(performance_delta, 2) if performance_delta is not None else None,
                "performance_data_state": performance_data_state,
                "performance_confidence": performance_confidence(int(rates["underlying_minutes"]) if rates else 0),
                "performance_sample_gameweeks": int(rates["underlying_gameweeks"]) if rates else 0,
                "performance_sample_minutes": int(rates["underlying_minutes"]) if rates else 0,
                "performance_model_version": PERFORMANCE_MODEL_VERSION,
                "prior_source": rates["prior_source"] if rates else None,
                "prior_confidence": rates["prior_confidence"] if rates else None,
                "prior_minutes": int(rates["prior_minutes"]) if rates else 0,
                "prior_seasons": rates["prior_seasons"] if rates else None,
                "prior_model_version": rates["prior_model_version"] if rates else None,
                "fixture_projection": fixture_projection,
                "forward_delta": round(buy_delta_6, 2),
                "value_trend": round(value_trend, 2),
                "price_trend": round(price_trends.get(row["player_id"], 0.0) or 0.0, 2),
                "is_emerging": historical_delta is not None and historical_delta < 0 and buy_delta_6 > 0,
                "is_regression_risk": historical_delta is not None and historical_delta > 0 and buy_delta_6 < 0,
                "captain_adjusted_delta": round(captain_delta, 2),
                "opportunity_score": round(opportunity_score, 2),
                "expected_minutes": round(expected_minutes, 1),
                "xg90": round(rates["xg90"], 2) if rates else None,
                "xa90": round(rates["xa90"], 2) if rates else None,
                "raw_xg": round(rates["raw_xg"], 2) if rates else None,
                "raw_xa": round(rates["raw_xa"], 2) if rates else None,
                "role_xppg": round(role_boost, 2),
                "clean_sheet_xppg_3": round(clean_sheet_3, 2),
                "clean_sheet_xppg_6": round(clean_sheet_6, 2),
                "defcon_xppg": round(defcon, 2),
                "bonus_xppg": round(bonus, 2),
                "save_xppg": round(observed_saves, 2),
                "expected_opponent_goals_6": round(sum((opponent_goals + [1.35] * 6)[:6]) / 6, 2),
                "role_override_reason": role["reason"] if role else None,
                **{key: role[key] if role else 0 for key in ROLE_KEYS},
                "start_probability": round(minute_profile["start_probability"], 2),
                "minutes_confidence": "HIGH" if minutes_confidence >= 0.75 else "MEDIUM" if minutes_confidence >= 0.5 else "LOW",
                "minutes_override_reason": override["reason"] if override else None,
                "fixture_factor_3": round(sum((fixture_factors + [1.0, 1.0, 1.0])[:3]) / 3, 2),
                "fixture_factor_6": round(sum((fixture_factors + [1.0] * 6)[:6]) / 6, 2),
                "projection_confidence": round(confidence, 2),
                "par_confidence": par_confidence,
                "ownership": row["ownership"],
                "status": player_status(buy_delta_6, buy_delta_3, confidence, (actual - market_mean) if actual is not None else 0),
            }
        )
    return sorted(board, key=lambda item: item["buy_delta_6"], reverse=True)[:limit]


def breakout_board(
    con: sqlite3.Connection,
    season: str,
    par_season: str = "2026-27",
    gameweeks_played: int | None = None,
    limit: int = 50,
    as_of_gw: int | None = None,
):
    rows = buy_board(con, season, par_season, gameweeks_played, 2000, as_of_gw)
    breakouts = [
        row | {"breakout_gap": round(row["next_6_xppg"] - row["actual_ppg"], 2)}
        for row in rows
        if row["actual_ppg"] is not None and row["next_6_xppg"] > row["value_par"] and row["actual_ppg"] < row["next_6_xppg"]
    ]
    return sorted(breakouts, key=lambda row: (row["breakout_gap"], row["buy_delta_6"]), reverse=True)[:limit]


def trap_board(
    con: sqlite3.Connection,
    season: str,
    par_season: str = "2026-27",
    gameweeks_played: int | None = None,
    limit: int = 50,
    as_of_gw: int | None = None,
):
    rows = buy_board(con, season, par_season, gameweeks_played, 2000, as_of_gw)
    traps = [
        row | {"trap_gap": round(row["actual_ppg"] - row["next_6_xppg"], 2)}
        for row in rows
        if row["actual_ppg"] is not None and row["actual_ppg"] > row["value_par"] and row["next_6_xppg"] < row["value_par"]
    ]
    return sorted(traps, key=lambda row: (row["trap_gap"], -row["buy_delta_6"]), reverse=True)[:limit]
