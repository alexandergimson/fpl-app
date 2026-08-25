from __future__ import annotations

import sqlite3

from backend.models.config import PLAYER_ATTACK_PRIOR_MINUTES, TEAM_DEFENCE_PRIOR_MATCHES
from backend.models.projections import clean_sheet_ev


GOAL_POINTS = {"GK": 6, "DEF": 6, "MID": 5, "FWD": 4}
PERFORMANCE_MODEL_VERSION = "player_process_v3"
UNDERLYING_COMPONENTS_VERSION = "underlying_components_v2"


def regressed_rate(raw: float, minutes: int, prior: float, prior_minutes: int = PLAYER_ATTACK_PRIOR_MINUTES) -> float:
    return (raw * minutes + prior * prior_minutes) / (minutes + prior_minutes) if minutes > 0 else prior


def rate_dict(row: sqlite3.Row) -> dict[str, float]:
    minutes = row["minutes"] or 0
    return {
        "xg90": ((row["xg"] or 0) / minutes * 90) if minutes > 0 else 0.0,
        "xa90": ((row["xa"] or 0) / minutes * 90) if minutes > 0 else 0.0,
        "cbit90": ((row["cbit"] or 0) / minutes * 90) if minutes > 0 else 0.0,
        "cbirt90": ((row["cbirt"] or 0) / minutes * 90) if minutes > 0 else 0.0,
        "minutes": minutes,
    }


def player_underlying_rates(con: sqlite3.Connection, season: str, through_gw: int | None = None) -> dict[int, dict[str, float]]:
    clause = "AND gameweek <= ?" if through_gw is not None else ""
    params = (season, through_gw) if through_gw is not None else (season,)
    prior_season = f"{int(season[:4]) - 1}-{str(int(season[:4]))[-2:]}" if season[:4].isdigit() else ""
    cohort_rows = con.execute(
        """
        SELECT cur.player_id, SUM(u.minutes) AS minutes, SUM(u.xg) AS xg, SUM(u.xa) AS xa, SUM(u.cbit) AS cbit, SUM(u.cbirt) AS cbirt
        FROM players cur
        JOIN players hist
          ON hist.season = ? AND hist.position = cur.position
         AND ROUND(hist.current_price * 2) / 2 = ROUND(cur.current_price * 2) / 2
        JOIN player_underlying_gameweeks u ON u.season = hist.season AND u.player_id = hist.player_id
        WHERE cur.season = ? AND u.xg_observed = 1 AND u.xa_observed = 1
        GROUP BY cur.player_id
        """,
        (prior_season, season),
    ).fetchall()
    position_rows = con.execute(
        """
        SELECT cur.player_id, SUM(u.minutes) AS minutes, SUM(u.xg) AS xg, SUM(u.xa) AS xa, SUM(u.cbit) AS cbit, SUM(u.cbirt) AS cbirt
        FROM players cur
        JOIN players hist ON hist.season = ? AND hist.position = cur.position
        JOIN player_underlying_gameweeks u ON u.season = hist.season AND u.player_id = hist.player_id
        WHERE cur.season = ? AND u.xg_observed = 1 AND u.xa_observed = 1
        GROUP BY cur.player_id
        """,
        (prior_season, season),
    ).fetchall()
    cohort_priors = {row["player_id"]: rate_dict(row) for row in cohort_rows if (row["minutes"] or 0) > 0}
    position_priors = {row["player_id"]: rate_dict(row) for row in position_rows if (row["minutes"] or 0) > 0}
    prior_rows = con.execute(
        """
        SELECT cur.player_id, SUM(u.minutes) AS minutes, SUM(u.xg) AS xg, SUM(u.xa) AS xa,
               SUM(u.cbit) AS cbit, SUM(u.cbirt) AS cbirt
        FROM players cur
        JOIN players prev ON prev.code = cur.code AND prev.season = ?
        JOIN player_underlying_gameweeks u ON u.season = prev.season AND u.player_id = prev.player_id
        WHERE cur.season = ? AND cur.code IS NOT NULL
        GROUP BY cur.player_id
        """,
        (prior_season, season),
    ).fetchall()
    player_priors = {row["player_id"]: rate_dict(row) for row in prior_rows if (row["minutes"] or 0) > 0}
    rows = con.execute(
        f"""
        SELECT u.player_id, p.position, COUNT(DISTINCT u.gameweek) AS gameweeks,
               SUM(u.minutes) AS minutes, SUM(u.xg) AS xg, SUM(u.xa) AS xa, SUM(u.cbit) AS cbit, SUM(u.cbirt) AS cbirt,
               MAX(u.xg_observed) AS xg_observed, MAX(u.xa_observed) AS xa_observed,
               MAX(u.cbit_observed) AS cbit_observed, MAX(u.cbirt_observed) AS cbirt_observed
        FROM player_underlying_gameweeks u
        JOIN players p ON p.season = u.season AND p.player_id = u.player_id
        WHERE u.season = ? {clause}
        GROUP BY u.player_id, p.position
        """,
        params,
    ).fetchall()
    rates = {}
    for row in rows:
        minutes = row["minutes"] or 0
        if minutes <= 0:
            continue
        player_prior = player_priors.get(row["player_id"])
        cohort_prior = cohort_priors.get(row["player_id"])
        position_prior = position_priors.get(row["player_id"])
        prior = player_prior or cohort_prior or position_prior or {}
        prior_minutes = min(PLAYER_ATTACK_PRIOR_MINUTES, int(prior.get("minutes", 0)))
        prior_source = "player_history" if player_prior else "historical_position_price" if cohort_prior else "historical_position" if position_prior else "none"
        rates[row["player_id"]] = {
            "xg90": regressed_rate((row["xg"] or 0) / minutes * 90, minutes, prior.get("xg90", 0.0), prior_minutes),
            "xa90": regressed_rate((row["xa"] or 0) / minutes * 90, minutes, prior.get("xa90", 0.0), prior_minutes),
            "cbit90": regressed_rate((row["cbit"] or 0) / minutes * 90, minutes, prior.get("cbit90", 0.0), prior_minutes),
            "cbirt90": regressed_rate((row["cbirt"] or 0) / minutes * 90, minutes, prior.get("cbirt90", 0.0), prior_minutes),
            "raw_xg": row["xg"] or 0.0,
            "raw_xa": row["xa"] or 0.0,
            "raw_cbit": row["cbit"] or 0.0,
            "raw_cbirt": row["cbirt"] or 0.0,
            "has_attack_observation": bool(row["xg_observed"] and row["xa_observed"]),
            "has_defcon_observation": bool(row["cbit_observed"] or row["cbirt_observed"]),
            "prior_source": prior_source,
            "prior_confidence": "HIGH" if player_prior and prior.get("minutes", 0) >= 900 else "LOW" if not player_prior else "MEDIUM",
            "prior_minutes": int(prior.get("minutes", 0)),
            "prior_seasons": prior_season if prior_source != "none" else "",
            "prior_model_version": "historical_position_price_v1",
            "underlying_minutes": minutes,
            "underlying_gameweeks": row["gameweeks"] or 0,
        }
    return rates


def team_defensive_xga(con: sqlite3.Connection, season: str, through_gw: int | None = None) -> dict[int, float]:
    clause = "AND gameweek <= ?" if through_gw is not None else ""
    params = (season, through_gw) if through_gw is not None else (season,)
    rows = con.execute(
        f"""
        SELECT team_id, COUNT(*) AS matches, AVG(xga) AS xga
        FROM team_underlying_gameweeks
        WHERE season = ? {clause}
        GROUP BY team_id
        """,
        params,
    ).fetchall()
    league = sum(row["xga"] or 0 for row in rows) / len(rows) if rows else 1.35
    return {
        row["team_id"]: ((row["xga"] or league) * row["matches"] + league * TEAM_DEFENCE_PRIOR_MATCHES) / (row["matches"] + TEAM_DEFENCE_PRIOR_MATCHES)
        for row in rows
        if row["xga"] is not None
    }


def clean_sheet_process_xppg(position: str, expected_minutes: float, expected_goals_against: float | None, probability_of_60: float) -> float:
    points = 4 if position in {"GK", "DEF"} else 1 if position == "MID" else 0
    return clean_sheet_ev(expected_goals_against if expected_goals_against is not None else 1.35, points, probability_of_60) if points else 0.0


def calculate_game_underlying_components(
    position: str,
    minutes: int,
    xg: float,
    xa: float,
    cbit: float | None = None,
    cbirt: float | None = None,
    expected_goals_against: float | None = None,
    bonus_ev: float = 0.0,
    save_ev: float = 0.0,
    deduction_ev: float = 0.0,
) -> dict[str, float]:
    parts = underlying_xpts_components(position, minutes, xg, xa, cbit, cbirt)
    p60 = 1.0 if minutes >= 60 else 0.0
    parts["clean_sheet_process_ev"] = clean_sheet_process_xppg(position, minutes, expected_goals_against, p60) if expected_goals_against is not None else 0.0
    parts["bonus_process_ev"] = max(0.0, bonus_ev)
    parts["save_process_ev"] = max(0.0, save_ev)
    parts["deduction_process_ev"] = min(0.0, deduction_ev)
    parts["game_underlying_xpts"] = sum(parts.values())
    return parts


def performance_confidence(sample_minutes: int) -> str:
    if sample_minutes >= 900:
        return "HIGH"
    if sample_minutes >= 360:
        return "MEDIUM"
    return "LOW"


def performance_evidence_state(position: str, rates: dict[str, float] | None, has_team_defence: bool = False, has_save_process: bool = False) -> str:
    if not rates or rates.get("underlying_minutes", 0) <= 0 or rates.get("underlying_gameweeks", 0) <= 0:
        return "missing"
    has_attack = bool(rates.get("has_attack_observation"))
    has_defcon = bool(rates.get("has_defcon_observation"))
    if position in {"MID", "FWD"}:
        return "sufficient" if has_attack else "partial"
    if position == "DEF":
        if not has_attack and not has_defcon:
            return "missing"
        return "sufficient" if has_team_defence else "partial"
    if position == "GK":
        return "sufficient" if has_team_defence and has_save_process else "partial"
    return "missing"


def attacking_xppg(position: str, expected_minutes: float, xg90: float, xa90: float) -> float:
    minutes_factor = max(0.0, expected_minutes) / 90
    return minutes_factor * (xg90 * GOAL_POINTS.get(position, 4) + xa90 * 3)


def defcon_xppg(position: str, expected_minutes: float, cbit90: float, cbirt90: float) -> float:
    threshold = 10 if position == "DEF" else 12 if position in {"MID", "FWD"} else 0
    rate = cbit90 if position == "DEF" else cbirt90
    if not threshold or rate <= 0:
        return 0.0
    probability = max(0.0, min(1.0, rate / threshold))
    return min(1.0, expected_minutes / 60) * probability * 2


def underlying_xpts_components(position: str, minutes: int, xg: float, xa: float, cbit: float | None = None, cbirt: float | None = None) -> dict[str, float]:
    appearance = min(2.0, 2.0 * max(0, minutes) / 90)
    goal = max(0.0, xg) * GOAL_POINTS.get(position, 4)
    assist = max(0.0, xa) * 3
    threshold = 10 if position == "DEF" else 12 if position in {"MID", "FWD"} else 0
    actions = cbit if position == "DEF" else cbirt
    defcon = 0.0 if not threshold or actions is None else max(0.0, min(1.0, actions / threshold)) * 2
    return {
        "appearance_ev": appearance,
        "goal_ev": goal,
        "assist_ev": assist,
        "clean_sheet_process_ev": 0.0,  # ponytail: needs provider xGA/P(CS), keep zero until real process data lands.
        "defcon_ev": defcon,
        "bonus_process_ev": 0.0,  # ponytail: no expected bonus feed yet; do not store actual bonus as process.
        "save_process_ev": 0.0,  # ponytail: no expected save feed yet; do not store actual saves as process.
        "deduction_process_ev": 0.0,
    }


def rebuild_game_underlying_xpts(con: sqlite3.Connection, season: str, source: str | None = None) -> int:
    clause = "AND u.source = ?" if source else ""
    params = (season, source) if source else (season,)
    rows = con.execute(
        f"""
        SELECT u.player_id, u.gameweek, u.source, u.minutes, u.xg, u.xa, u.cbit, u.cbirt,
               u.fetched_at, u.data_period, p.position, COALESCE(tx.xga, 1.35) AS expected_goals_against,
               COALESCE(pg.saves, 0) AS saves
        FROM player_underlying_gameweeks u
        JOIN players p ON p.season = u.season AND p.player_id = u.player_id
        LEFT JOIN team_underlying_gameweeks tx ON tx.season = u.season AND tx.team_id = p.team_id AND tx.gameweek = u.gameweek
        LEFT JOIN player_gameweeks pg ON pg.season = u.season AND pg.player_id = u.player_id AND pg.gameweek = u.gameweek
        WHERE u.season = ? {clause}
        """,
        params,
    ).fetchall()
    if source:
        con.execute("DELETE FROM game_underlying_xpts WHERE season = ? AND source = ?", (season, source))
    else:
        con.execute("DELETE FROM game_underlying_xpts WHERE season = ?", (season,))
    inserts = []
    for row in rows:
        parts = calculate_game_underlying_components(
            row["position"],
            row["minutes"],
            row["xg"],
            row["xa"],
            row["cbit"],
            row["cbirt"],
            row["expected_goals_against"],
            save_ev=(row["saves"] or 0) / 3 if row["position"] == "GK" else 0.0,
        )
        inserts.append(
            (
                season,
                row["player_id"],
                row["gameweek"],
                row["source"],
                row["minutes"],
                round(parts["appearance_ev"], 2),
                round(parts["goal_ev"], 2),
                round(parts["assist_ev"], 2),
                round(parts["clean_sheet_process_ev"], 2),
                round(parts["defcon_ev"], 2),
                round(parts["bonus_process_ev"], 2),
                round(parts["save_process_ev"], 2),
                round(parts["deduction_process_ev"], 2),
                round(parts["game_underlying_xpts"], 2),
                row["fetched_at"],
                row["data_period"],
            )
        )
    con.executemany(
        """
        INSERT OR REPLACE INTO game_underlying_xpts (
          season, player_id, gameweek, source, minutes, appearance_ev, goal_ev,
          assist_ev, clean_sheet_process_ev, defcon_ev, bonus_process_ev,
          save_process_ev, deduction_process_ev, game_underlying_xpts, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        inserts,
    )
    con.commit()
    return len(inserts)
