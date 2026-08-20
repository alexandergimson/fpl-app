from __future__ import annotations

import sqlite3

from backend.models.price_par import ParPoint
from backend.models.projections import role_xppg
from backend.services.bonus import bonus_rates, bonus_xppg
from backend.services.fixtures import adjusted_horizon_ppg, clean_sheet_horizon_ev, upcoming_expected_opponent_goals, upcoming_fixture_factors
from backend.services.goalkeepers import save_rates, save_xppg
from backend.services.history import player_totals_as_of
from backend.services.minutes import latest_minutes_overrides
from backend.services.price_par import blended_par_for, current_curve_points
from backend.services.roles import ROLE_KEYS, latest_role_overrides
from backend.services.underlying import attacking_xppg, defcon_xppg, player_underlying_rates
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
    bonus90_by_player = bonus_rates(con, season, as_of_gw)
    saves90_by_player = save_rates(con, season, as_of_gw)
    overrides = latest_minutes_overrides(con, season)
    roles = latest_role_overrides(con, season)
    current_par_points = current_curve_points(con, season, as_of_gw) if as_of_gw is not None else None
    denominator = gameweeks_played or as_of_gw or infer_gameweeks(rows, season, par_season)
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
        actual_ppg = points / max(1, denominator)
        minutes_confidence = min(1.0, minutes / max(1, denominator * 90))
        neutral_xppg = actual_ppg * (0.35 + 0.65 * minutes_confidence) + market_mean * (1 - minutes_confidence) * 0.35
        expected_minutes = minutes / max(1, denominator)
        override = overrides.get(row["player_id"])
        if override:
            expected_minutes = override["expected_minutes"]
            minutes_confidence = max(minutes_confidence, 0.75)
        rates = underlying.get(row["player_id"])
        bonus = bonus_xppg(expected_minutes, bonus90_by_player.get(row["player_id"], 0.0))
        saves = save_xppg(row["position"], expected_minutes, saves90_by_player.get(row["player_id"], 0.0))
        if rates:
            appearance = min(2.0, 2.0 * expected_minutes / 90)
            attack = attacking_xppg(row["position"], expected_minutes, rates["xg90"], rates["xa90"])
            defcon = defcon_xppg(row["position"], expected_minutes, rates["cbit90"], rates["cbirt90"])
            neutral_xppg = max(neutral_xppg * 0.5, appearance + attack + defcon + bonus + saves + max(0.0, market_mean - 2.0) * 0.25)
        else:
            defcon = 0.0
        role = roles.get(row["player_id"])
        role_boost = role_xppg(row["position"], expected_minutes, role)
        neutral_xppg += role_boost
        fixture_factors = upcoming_fixture_factors(con, season, row["team_id"], 6)
        opponent_goals = upcoming_expected_opponent_goals(con, season, row["team_id"], 6)
        neutral_clean_sheet = clean_sheet_horizon_ev([], row["position"], expected_minutes, 1)
        clean_sheet_3 = clean_sheet_horizon_ev(opponent_goals, row["position"], expected_minutes, 3)
        clean_sheet_6 = clean_sheet_horizon_ev(opponent_goals, row["position"], expected_minutes, 6)
        open_play_xppg = max(0.0, neutral_xppg - neutral_clean_sheet)
        next_3_xppg = adjusted_horizon_ppg(open_play_xppg, fixture_factors, 3) + clean_sheet_3
        next_6_xppg = adjusted_horizon_ppg(open_play_xppg, fixture_factors, 6) + clean_sheet_6
        buy_delta_3 = next_3_xppg - value_par
        buy_delta_6 = next_6_xppg - value_par
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
                "actual_ppg": round(actual_ppg, 2),
                "neutral_xppg": round(neutral_xppg, 2),
                "next_3_xppg": round(next_3_xppg, 2),
                "next_6_xppg": round(next_6_xppg, 2),
                "buy_delta_3": round(buy_delta_3, 2),
                "buy_delta_6": round(buy_delta_6, 2),
                "captain_adjusted_delta": round(captain_delta, 2),
                "opportunity_score": round(opportunity_score, 2),
                "expected_minutes": round(expected_minutes, 1),
                "xg90": round(rates["xg90"], 2) if rates else None,
                "xa90": round(rates["xa90"], 2) if rates else None,
                "role_xppg": round(role_boost, 2),
                "clean_sheet_xppg_3": round(clean_sheet_3, 2),
                "clean_sheet_xppg_6": round(clean_sheet_6, 2),
                "defcon_xppg": round(defcon, 2),
                "bonus_xppg": round(bonus, 2),
                "save_xppg": round(saves, 2),
                "expected_opponent_goals_6": round(sum((opponent_goals + [1.35] * 6)[:6]) / 6, 2),
                "role_override_reason": role["reason"] if role else None,
                **{key: role[key] if role else 0 for key in ROLE_KEYS},
                "start_probability": round(override["start_probability"] if override else min(1.0, minutes / max(1, denominator * 60)), 2),
                "minutes_confidence": "HIGH" if minutes_confidence >= 0.75 else "MEDIUM" if minutes_confidence >= 0.5 else "LOW",
                "minutes_override_reason": override["reason"] if override else None,
                "fixture_factor_3": round(sum((fixture_factors + [1.0, 1.0, 1.0])[:3]) / 3, 2),
                "fixture_factor_6": round(sum((fixture_factors + [1.0] * 6)[:6]) / 6, 2),
                "projection_confidence": round(confidence, 2),
                "par_confidence": par_confidence,
                "ownership": row["ownership"],
                "status": player_status(buy_delta_6, buy_delta_3, confidence, actual_ppg - market_mean),
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
        if row["next_6_xppg"] > row["value_par"] and row["actual_ppg"] < row["next_6_xppg"]
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
        if row["actual_ppg"] > row["value_par"] and row["next_6_xppg"] < row["value_par"]
    ]
    return sorted(traps, key=lambda row: (row["trap_gap"], -row["buy_delta_6"]), reverse=True)[:limit]
