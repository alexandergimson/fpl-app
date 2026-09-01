from __future__ import annotations

import sqlite3


RATE_METRICS = {
    "xg": "xG",
    "xa": "xA",
    "shots": "Shots",
    "shots_in_box": "Shots in box",
    "shots_on_target": "Shots on target",
    "key_passes": "Key passes",
    "saves": "Saves",
    "bps": "BPS",
    "penalty_shots": "Penalties taken",
    "direct_free_kick_shots": "Direct free kicks taken",
}

HEADLINE_METRICS = {
    "GK": ["saves", "bps"],
    "DEF": ["xg", "xa", "shots", "shots_in_box", "shots_on_target", "key_passes"],
    "MID": ["xg", "xa", "shots", "shots_in_box", "shots_on_target", "key_passes"],
    "FWD": ["xg", "xa", "shots", "shots_in_box", "shots_on_target", "key_passes"],
}


def benchmark_minutes(gameweek: int) -> int:
    return 45 if gameweek == 1 else 90 if gameweek == 2 else 180


def percentile(value: float, values: list[float]) -> int | None:
    if not values:
        return None
    lower = sum(item < value for item in values)
    equal = sum(item == value for item in values)
    return round((lower + equal / 2) / len(values) * 100)


def _game_rows(con: sqlite3.Connection, season: str, position: str) -> list[dict]:
    rows = con.execute(
        """
        WITH actual AS (
          SELECT player_id, gameweek, SUM(minutes) AS minutes, SUM(total_points) AS points,
                 SUM(starts) AS starts, SUM(goals_scored) AS goals, SUM(assists) AS assists,
                 SUM(bonus) AS bonus, SUM(bps) AS bps, SUM(saves) AS saves,
                 SUM(clean_sheets) AS clean_sheets, SUM(goals_conceded) AS goals_conceded,
                 GROUP_CONCAT(DISTINCT opponent_team) AS opponents
          FROM player_gameweeks WHERE season = ? GROUP BY player_id, gameweek
        ),
        underlying AS (
          SELECT player_id, gameweek, SUM(xg) AS xg, SUM(xa) AS xa
          FROM player_underlying_gameweeks WHERE season = ? GROUP BY player_id, gameweek
        ),
        shots AS (
          SELECT player_id, gameweek, SUM(shots) AS shots, SUM(shots_in_box) AS shots_in_box,
                 SUM(shots_on_target) AS shots_on_target, SUM(key_passes) AS key_passes,
                 SUM(penalty_shots) AS penalty_shots, SUM(penalty_xg) AS penalty_xg,
                 SUM(direct_free_kick_shots) AS direct_free_kick_shots,
                 SUM(xg) AS shot_xg, SUM(xa) AS shot_xa
          FROM player_shot_gameweeks WHERE season = ? GROUP BY player_id, gameweek
        ),
        performance AS (
          SELECT player_id, gameweek, SUM(game_underlying_xpts) AS performance_points
          FROM game_underlying_xpts WHERE season = ? GROUP BY player_id, gameweek
        )
        SELECT p.player_id, p.web_name AS player, p.team, p.team_id, p.current_price, p.position,
               a.gameweek, a.minutes, a.points, a.starts, a.goals, a.assists, a.bonus, a.bps,
               a.saves, a.clean_sheets, a.goals_conceded, a.opponents,
               COALESCE(u.xg, s.shot_xg) AS xg, COALESCE(u.xa, s.shot_xa) AS xa,
               s.shots, s.shots_in_box, s.shots_on_target, s.key_passes,
               s.penalty_shots, s.penalty_xg, s.direct_free_kick_shots,
               perf.performance_points, tu.xga AS team_xg_conceded
        FROM actual a
        JOIN players p ON p.season = ? AND p.player_id = a.player_id
        LEFT JOIN underlying u ON u.player_id = a.player_id AND u.gameweek = a.gameweek
        LEFT JOIN shots s ON s.player_id = a.player_id AND s.gameweek = a.gameweek
        LEFT JOIN performance perf ON perf.player_id = a.player_id AND perf.gameweek = a.gameweek
        LEFT JOIN team_underlying_gameweeks tu ON tu.season = ? AND tu.team_id = p.team_id AND tu.gameweek = a.gameweek
        WHERE p.position = ?
        ORDER BY a.gameweek, p.player_id
        """,
        (season, season, season, season, season, season, position),
    ).fetchall()
    return [dict(row) for row in rows]


def _opponent(con: sqlite3.Connection, season: str, team_id: int, gameweek: int) -> str | None:
    row = con.execute(
        """
        SELECT CASE WHEN f.team_h = ? THEN away.short_name ELSE home.short_name END AS opponent,
               CASE WHEN f.team_h = ? THEN 'H' ELSE 'A' END AS venue
        FROM fixtures f
        LEFT JOIN teams home ON home.season = f.season AND home.team_id = f.team_h
        LEFT JOIN teams away ON away.season = f.season AND away.team_id = f.team_a
        WHERE f.season = ? AND f.gameweek = ? AND (f.team_h = ? OR f.team_a = ?)
        LIMIT 1
        """,
        (team_id, team_id, season, gameweek, team_id, team_id),
    ).fetchone()
    return f"{row['opponent']} ({row['venue']})" if row and row["opponent"] else None


def player_analysis(con: sqlite3.Connection, season: str, player_id: int) -> dict | None:
    player = con.execute("SELECT player_id, web_name, team, team_id, position, current_price FROM players WHERE season = ? AND player_id = ?", (season, player_id)).fetchone()
    if not player:
        return None
    current = con.execute(
        """
        SELECT actual_ppg, current_par AS par_ppg,
               CASE WHEN performance_data_state = 'sufficient' THEN underlying_xppg END AS performance_ppg,
               next_6_xppg AS next_6_ppg, return_delta, performance_delta, forward_delta,
               performance_data_state
        FROM current_player_metrics WHERE season = ? AND player_id = ?
        """,
        (season, player_id),
    ).fetchone()
    headline = dict(current) if current else {"actual_ppg": None, "par_ppg": None, "performance_ppg": None, "next_6_ppg": None, "return_delta": None, "performance_delta": None, "forward_delta": None, "performance_data_state": "missing"}
    actual_ppg = headline.get("actual_ppg")
    performance_ppg = headline.get("performance_ppg")
    headline["process_gap"] = performance_ppg - actual_ppg if performance_ppg is not None and actual_ppg is not None else None
    if performance_ppg is None:
        diagnosis = "Insufficient process evidence"
    elif headline["performance_delta"] is not None and headline["performance_delta"] < -0.3:
        diagnosis = "Below positional benchmark"
    elif headline["process_gap"] > 0.5:
        diagnosis = "Strong process, weak returns"
    elif headline["process_gap"] < -0.5:
        diagnosis = "Returns ahead of process"
    else:
        diagnosis = "Returns supported by process"
    all_rows = _game_rows(con, season, player["position"])
    running_minutes: dict[int, int] = {}
    cumulative_minutes = {}
    for item in all_rows:
        running_minutes[item["player_id"]] = running_minutes.get(item["player_id"], 0) + (item["minutes"] or 0)
        cumulative_minutes[(item["player_id"], item["gameweek"])] = running_minutes[item["player_id"]]
    cumulative_actual = 0.0
    cumulative_performance = 0.0
    games = []
    for row in all_rows:
        if row["player_id"] != player_id:
            continue
        gw = row["gameweek"]
        threshold = benchmark_minutes(gw)
        eligible = cumulative_minutes[(player_id, gw)] >= threshold
        cohort = [item for item in all_rows if item["gameweek"] == gw and cumulative_minutes.get((item["player_id"], gw), 0) >= threshold and (item["minutes"] or 0) > 0]
        comparisons = []
        for key, label in RATE_METRICS.items():
            raw = row.get(key)
            if raw is None:
                continue
            per90 = raw / row["minutes"] * 90 if row["minutes"] else None
            peers = [item[key] / item["minutes"] * 90 for item in cohort if item.get(key) is not None and item["minutes"]]
            price_peers = [item for item in cohort if abs(item["current_price"] - player["current_price"]) <= 0.5]
            band = 0.5
            if len(price_peers) < 5:
                price_peers = [item for item in cohort if abs(item["current_price"] - player["current_price"]) <= 1.0]
                band = 1.0
            price_rates = [item[key] / item["minutes"] * 90 for item in price_peers if item.get(key) is not None and item["minutes"]]
            comparisons.append({
                "key": key,
                "label": label,
                "raw": round(raw, 2),
                "per_90": round(per90, 2) if per90 is not None else None,
                "positional_average": round(sum(peers) / len(peers), 2) if peers else None,
                "percentile": percentile(per90, peers) if eligible and per90 is not None else None,
                "price_average": round(sum(price_rates) / len(price_rates), 2) if price_rates else None,
                "price_band": band,
                "cohort_size": len(peers),
            })
        cumulative_actual += row["points"] or 0
        cumulative_performance += row["performance_points"] or 0
        games.append({
            **row,
            "opponent": _opponent(con, season, player["team_id"], gw),
            "xgi": round((row.get("xg") or 0) + (row.get("xa") or 0), 2) if row.get("xg") is not None or row.get("xa") is not None else None,
            "actual_minus_performance": round(row["points"] - row["performance_points"], 2) if row["performance_points"] is not None else None,
            "cumulative_actual_ppg": round(cumulative_actual / gw, 2),
            "cumulative_performance_ppg": round(cumulative_performance / gw, 2),
            "benchmark_eligible": eligible,
            "benchmark_minutes": threshold,
            "headline_metric_keys": HEADLINE_METRICS[player["position"]],
            "comparisons": comparisons,
        })
    return {"player": dict(player), "headline": headline, "diagnosis": diagnosis, "games": games}
