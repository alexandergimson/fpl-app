from __future__ import annotations

import sqlite3


GOAL_POINTS = {"GK": 6, "DEF": 6, "MID": 5, "FWD": 4}


def player_underlying_rates(con: sqlite3.Connection, season: str, through_gw: int | None = None) -> dict[int, dict[str, float]]:
    clause = "AND gameweek <= ?" if through_gw is not None else ""
    params = (season, through_gw) if through_gw is not None else (season,)
    rows = con.execute(
        f"""
        SELECT player_id, SUM(minutes) AS minutes, SUM(xg) AS xg, SUM(xa) AS xa, SUM(cbit) AS cbit, SUM(cbirt) AS cbirt
        FROM player_underlying_gameweeks
        WHERE season = ? {clause}
        GROUP BY player_id
        """,
        params,
    ).fetchall()
    rates = {}
    for row in rows:
        minutes = row["minutes"] or 0
        if minutes <= 0:
            continue
        rates[row["player_id"]] = {
            "xg90": (row["xg"] or 0) / minutes * 90,
            "xa90": (row["xa"] or 0) / minutes * 90,
            "cbit90": (row["cbit"] or 0) / minutes * 90,
            "cbirt90": (row["cbirt"] or 0) / minutes * 90,
            "underlying_minutes": minutes,
        }
    return rates


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
    }


def rebuild_game_underlying_xpts(con: sqlite3.Connection, season: str, source: str | None = None) -> int:
    clause = "AND u.source = ?" if source else ""
    params = (season, source) if source else (season,)
    rows = con.execute(
        f"""
        SELECT u.player_id, u.gameweek, u.source, u.minutes, u.xg, u.xa, u.cbit, u.cbirt,
               u.fetched_at, u.data_period, p.position
        FROM player_underlying_gameweeks u
        JOIN players p ON p.season = u.season AND p.player_id = u.player_id
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
        parts = underlying_xpts_components(row["position"], row["minutes"], row["xg"], row["xa"], row["cbit"], row["cbirt"])
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
                round(sum(parts.values()), 2),
                row["fetched_at"],
                row["data_period"],
            )
        )
    con.executemany(
        """
        INSERT OR REPLACE INTO game_underlying_xpts (
          season, player_id, gameweek, source, minutes, appearance_ev, goal_ev,
          assist_ev, clean_sheet_process_ev, defcon_ev, bonus_process_ev,
          save_process_ev, game_underlying_xpts, fetched_at, data_period
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        inserts,
    )
    con.commit()
    return len(inserts)
