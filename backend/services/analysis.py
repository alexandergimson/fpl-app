from __future__ import annotations

import sqlite3


RATE_METRICS = {
    "xg": ("xG", "per90", False),
    "xa": ("xA", "per90", False),
    "shots": ("Shots", "per90", False),
    "shots_in_box": ("Shots in box", "per90", False),
    "shots_on_target": ("Shots on target", "per90", False),
    "xg_per_shot": ("xG / shot", "per_shot", False),
    "key_passes": ("Key passes", "per90", False),
    "saves": ("Saves", "per90", False),
    "bps": ("BPS", "per90", False),
    "clean_sheets": ("Clean sheets", "per90", False),
    "goals_conceded": ("Goals conceded", "per90", True),
    "team_xg_conceded": ("Team xGC", "per_game", True),
    "shots_faced": ("Shots faced", "per_game", True),
    "shots_on_target_faced": ("Shots on target faced", "per_game", True),
    "save_percentage": ("Save %", "save_percentage", False),
    "shots_conceded": ("Shots conceded", "per_game", True),
    "penalty_shots": ("Penalties taken", "per90", False),
    "direct_free_kick_shots": ("Direct free kicks taken", "per90", False),
}

POSITION_METRICS = {
    "GK": ["saves", "shots_faced", "shots_on_target_faced", "save_percentage", "goals_conceded", "clean_sheets", "team_xg_conceded", "bps"],
    "DEF": ["team_xg_conceded", "shots_conceded", "xg", "xa", "shots", "shots_in_box", "shots_on_target", "key_passes"],
    "MID": ["xg", "xa", "shots", "shots_in_box", "shots_on_target", "key_passes", "direct_free_kick_shots"],
    "FWD": ["xg", "shots", "shots_in_box", "shots_on_target", "xg_per_shot", "key_passes", "xa", "penalty_shots"],
}

HEADLINE_METRICS = {
    "GK": ["saves", "save_percentage", "team_xg_conceded", "bps"],
    "DEF": ["team_xg_conceded", "xg", "xa", "shots"],
    "MID": ["xg", "xa", "shots", "key_passes"],
    "FWD": ["xg", "shots", "shots_in_box", "xg_per_shot"],
}


def benchmark_minutes(gameweek: int) -> int:
    return 45 if gameweek == 1 else 90 if gameweek == 2 else 180


def percentile(value: float, values: list[float]) -> int | None:
    if not values:
        return None
    lower = sum(item < value for item in values)
    equal = sum(item == value for item in values)
    return round((lower + equal / 2) / len(values) * 100)


def _rate(metric: str, values: dict) -> float | None:
    _, basis, _ = RATE_METRICS[metric]
    if basis == "per_shot":
        return values.get("xg") / values["shots"] if not values.get("xg_missing") and not values.get("shots_missing") and values.get("xg") is not None and values.get("shots") else None
    if basis == "save_percentage":
        return values.get("saves") / values["shots_on_target_faced"] * 100 if not values.get("saves_missing") and not values.get("shots_on_target_faced_missing") and values.get("shots_on_target_faced") else None
    if values.get(f"{metric}_missing"):
        return None
    raw = values.get(metric)
    if raw is None:
        return None
    if basis == "per_game":
        games = values.get(f"{metric}_games", 0)
        return raw / games if games else None
    return raw / values["minutes"] * 90 if values.get("minutes") else None


def _cumulative_rows(rows: list[dict]) -> dict[tuple[int, int], dict]:
    running: dict[int, dict] = {}
    snapshots = {}
    metric_keys = set(RATE_METRICS) - {"xg_per_shot", "save_percentage"}
    for gameweek in sorted({row["gameweek"] for row in rows}):
        for row in (item for item in rows if item["gameweek"] == gameweek):
            totals = running.setdefault(row["player_id"], {"minutes": 0, "player_id": row["player_id"], "current_price": row["current_price"]})
            totals["minutes"] += row.get("minutes") or 0
            for key in metric_keys:
                if row.get(key) is not None:
                    totals[key] = totals.get(key, 0) + row[key]
                    totals[f"{key}_games"] = totals.get(f"{key}_games", 0) + 1
                else:
                    totals[f"{key}_missing"] = True
        for peer_id, totals in running.items():
            snapshots[(peer_id, gameweek)] = totals.copy()
    return snapshots


def _aggregate_rows(rows: list[dict]) -> dict:
    totals = {"minutes": 0}
    metric_keys = set(RATE_METRICS) - {"xg_per_shot", "save_percentage"}
    for row in rows:
        totals["minutes"] += row.get("minutes") or 0
        for key in metric_keys:
            if row.get(key) is None:
                totals[f"{key}_missing"] = True
            else:
                totals[key] = totals.get(key, 0) + row[key]
                totals[f"{key}_games"] = totals.get(f"{key}_games", 0) + 1
    return totals


def _window_rows(rows: list[dict], player_id: int, through_gameweek: int, window: str) -> list[dict]:
    played = [row for row in rows if row["player_id"] == player_id and row["gameweek"] <= through_gameweek and (row.get("minutes") or 0) > 0]
    return played[-5:] if window == "last5" else played


def _diagnosis(position: str, headline: dict, comparisons: list[dict]) -> str:
    percentiles = {item["key"]: item["percentile"] for item in comparisons if item["percentile"] is not None}
    groups = {
        "FWD": ("Strong goal threat", "Attacking process below the positional benchmark", ["xg", "shots", "shots_in_box", "shots_on_target"]),
        "MID": ("Strong attacking and creative output", "Attacking output below the positional benchmark", ["xg", "xa", "shots", "key_passes"]),
        "DEF": ("Strong defensive environment", "Defensive environment below the positional benchmark", ["team_xg_conceded", "shots_conceded"]),
        "GK": ("Strong shot-stopping evidence", "Shot-stopping evidence below the positional benchmark", ["saves", "save_percentage", "team_xg_conceded"]),
    }
    strong, weak, keys = groups[position]
    evidence = [percentiles[key] for key in keys if key in percentiles]
    evidence_text = f"{strong}." if len(evidence) >= 2 and sum(evidence) / len(evidence) >= 70 else f"{weak}." if len(evidence) >= 2 and sum(evidence) / len(evidence) <= 30 else ""
    if headline.get("performance_ppg") is None:
        process = ["Insufficient process evidence."]
    else:
        process = []
        if headline.get("process_gap", 0) > 0.5:
            process.append("Strong process, weak returns.")
        elif headline.get("process_gap", 0) < -0.5:
            process.append("Returns ahead of process.")
        if headline.get("performance_delta") is not None and headline["performance_delta"] < -0.3:
            process.append("Underlying performance below price expectation.")
        if not process:
            process.append("Returns supported by process.")
    return " ".join(item for item in (evidence_text, *process) if item)


def _comparisons(position: str, target: dict, cohort: list[dict], current_price: float, eligible: bool, aggregate: bool = False) -> tuple[list[dict], float, int]:
    price_peers = [item for item in cohort if abs(item["current_price"] - current_price) <= 0.5]
    band = 0.5
    if len(price_peers) < 5:
        price_peers = [item for item in cohort if abs(item["current_price"] - current_price) <= 1.0]
        band = 1.0
    comparisons = []
    for key in POSITION_METRICS[position]:
        label, basis, inverse = RATE_METRICS[key]
        player_rate = _rate(key, target)
        raw = player_rate if aggregate or basis in {"per_shot", "save_percentage"} else target.get(key)
        if raw is None:
            continue
        peers = [rate for item in cohort if (rate := _rate(key, item)) is not None]
        price_rates = [rate for item in price_peers if (rate := _rate(key, item)) is not None]
        ranked_rate = -player_rate if inverse and player_rate is not None else player_rate
        ranked_peers = [-rate for rate in peers] if inverse else peers
        comparisons.append({
            "key": key,
            "label": label,
            "raw": round(raw, 2),
            "per_90": round(player_rate, 2) if basis == "per90" and player_rate is not None else None,
            "positional_average": round(sum(peers) / len(peers), 2) if peers else None,
            "percentile": percentile(ranked_rate, ranked_peers) if eligible and ranked_rate is not None else None,
            "price_average": round(sum(price_rates) / len(price_rates), 2) if price_rates else None,
            "price_band": band,
            "cohort_size": len(peers),
            "rate_basis": basis,
        })
    return comparisons, band, len(price_peers)


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
               perf.performance_points, SUM(tu.xga) AS team_xg_conceded,
               SUM(tu.shots_conceded) AS shots_faced,
               SUM(tu.shots_on_target_conceded) AS shots_on_target_faced,
               SUM(tu.shots_conceded) AS shots_conceded
        FROM actual a
        JOIN players p ON p.season = ? AND p.player_id = a.player_id
        LEFT JOIN underlying u ON u.player_id = a.player_id AND u.gameweek = a.gameweek
        LEFT JOIN shots s ON s.player_id = a.player_id AND s.gameweek = a.gameweek
        LEFT JOIN performance perf ON perf.player_id = a.player_id AND perf.gameweek = a.gameweek
        LEFT JOIN team_underlying_gameweeks tu ON tu.season = ? AND tu.team_id = p.team_id AND tu.gameweek = a.gameweek
        WHERE p.position = ?
        GROUP BY p.player_id, a.gameweek
        ORDER BY a.gameweek, p.player_id
        """,
        (season, season, season, season, season, season, position),
    ).fetchall()
    return [dict(row) for row in rows]


def _opponent(con: sqlite3.Connection, season: str, team_id: int, gameweek: int) -> str | None:
    rows = con.execute(
        """
        SELECT CASE WHEN f.team_h = ? THEN away.short_name ELSE home.short_name END AS opponent,
               CASE WHEN f.team_h = ? THEN 'H' ELSE 'A' END AS venue
        FROM fixtures f
        LEFT JOIN teams home ON home.season = f.season AND home.team_id = f.team_h
        LEFT JOIN teams away ON away.season = f.season AND away.team_id = f.team_a
        WHERE f.season = ? AND f.gameweek = ? AND (f.team_h = ? OR f.team_a = ?)
        """,
        (team_id, team_id, season, gameweek, team_id, team_id),
    ).fetchall()
    return ", ".join(f"{row['opponent']} ({row['venue']})" for row in rows if row["opponent"]) or None


def player_analysis(con: sqlite3.Connection, season: str, player_id: int, window: str = "auto") -> dict | None:
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
    all_rows = _game_rows(con, season, player["position"])
    cumulative = _cumulative_rows(all_rows)
    player_rows = [row for row in all_rows if row["player_id"] == player_id]
    appearances = sum((row.get("minutes") or 0) > 0 for row in player_rows)
    selected_window = window if window in {"last5", "season"} else "last5" if appearances > 5 else "season"
    latest_gameweek = max((row["gameweek"] for row in player_rows), default=0)
    threshold = benchmark_minutes(latest_gameweek) if latest_gameweek else 0
    eligible = bool(latest_gameweek and cumulative[(player_id, latest_gameweek)]["minutes"] >= threshold)
    selected_rows = _window_rows(all_rows, player_id, latest_gameweek, selected_window)
    selected_values = _aggregate_rows(selected_rows)
    selected_values.update(player_id=player_id, current_price=player["current_price"])
    cohort = []
    if latest_gameweek:
        for (peer_id, peer_gw), season_values in cumulative.items():
            if peer_gw != latest_gameweek or season_values["minutes"] < threshold:
                continue
            peer_rows = _window_rows(all_rows, peer_id, latest_gameweek, selected_window)
            if not peer_rows:
                continue
            peer_values = _aggregate_rows(peer_rows)
            peer_values.update(player_id=peer_id, current_price=season_values["current_price"])
            cohort.append(peer_values)
    aggregate_comparisons, price_band, price_cohort_size = _comparisons(player["position"], selected_values, cohort, player["current_price"], eligible, aggregate=True)
    aggregate = {
        "window": selected_window,
        "available_windows": ["season", "last5"] if appearances > 5 else ["season"],
        "appearances": len(selected_rows),
        "minutes": selected_values["minutes"],
        "from_gameweek": selected_rows[0]["gameweek"] if selected_rows else None,
        "to_gameweek": selected_rows[-1]["gameweek"] if selected_rows else None,
        "benchmark_eligible": eligible,
        "benchmark_minutes": threshold,
        "cohort_size": len(cohort),
        "price_cohort_size": price_cohort_size,
        "price_band": price_band,
        "comparisons": aggregate_comparisons,
    }
    diagnosis = _diagnosis(player["position"], headline, aggregate_comparisons)
    cumulative_actual = 0.0
    cumulative_performance = 0.0
    games = []
    for row in all_rows:
        if row["player_id"] != player_id:
            continue
        gw = row["gameweek"]
        threshold = benchmark_minutes(gw)
        eligible = cumulative[(player_id, gw)]["minutes"] >= threshold
        cohort = [values for (peer_id, peer_gw), values in cumulative.items() if peer_gw == gw and values["minutes"] >= threshold]
        comparisons, _, _ = _comparisons(player["position"], row, cohort, player["current_price"], eligible)
        cumulative_actual += row["points"] or 0
        if row["performance_points"] is None:
            cumulative_performance = None
        elif cumulative_performance is not None:
            cumulative_performance += row["performance_points"]
        games.append({
            **row,
            "opponent": _opponent(con, season, player["team_id"], gw),
            "xgi": round((row.get("xg") or 0) + (row.get("xa") or 0), 2) if row.get("xg") is not None or row.get("xa") is not None else None,
            "actual_minus_performance": round(row["points"] - row["performance_points"], 2) if row["performance_points"] is not None else None,
            "cumulative_actual_ppg": round(cumulative_actual / gw, 2),
            "cumulative_performance_ppg": round(cumulative_performance / gw, 2) if cumulative_performance is not None else None,
            "benchmark_eligible": eligible,
            "benchmark_minutes": threshold,
            "headline_metric_keys": HEADLINE_METRICS[player["position"]],
            "comparisons": comparisons,
        })
    return {"player": dict(player), "headline": headline, "aggregate": aggregate, "diagnosis": diagnosis, "games": games}
