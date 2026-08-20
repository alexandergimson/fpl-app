from __future__ import annotations

import math
import sqlite3

from backend.services.boards import buy_board
from backend.services.history import future_points


WINDOWS = [(1, 5, 6, 10), (1, 10, 11, 16), (1, 15, 16, 21), (1, 20, 21, 26)]


def rmse(errors: list[float]) -> float:
    return math.sqrt(sum(error * error for error in errors) / len(errors)) if errors else 0.0


def mae(errors: list[float]) -> float:
    return sum(abs(error) for error in errors) / len(errors) if errors else 0.0


def ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    i = 0
    while i < len(ordered):
        j = i
        while j < len(ordered) and ordered[j][1] == ordered[i][1]:
            j += 1
        rank = (i + j + 1) / 2
        for index, _ in ordered[i:j]:
            result[index] = rank
        i = j
    return result


def spearman(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    numerator = sum((x - mx) * (y - my) for x, y in zip(rx, ry))
    dx = math.sqrt(sum((x - mx) ** 2 for x in rx))
    dy = math.sqrt(sum((y - my) ** 2 for y in ry))
    return numerator / (dx * dy) if dx and dy else 0.0


def evaluate_model(
    con: sqlite3.Connection,
    season: str,
    par_season: str,
    train_end: int,
    test_start: int,
    test_end: int,
    top_n: int,
    model: str,
    rank_key: str,
    prediction_key: str = "next_6_xppg",
) -> dict:
    horizon = test_end - test_start + 1
    all_rows = buy_board(con, season, par_season, None, 2000, as_of_gw=train_end)
    ranked_rows = sorted(all_rows, key=lambda row: row[rank_key], reverse=True)
    return evaluate_rows(con, season, ranked_rows, ranked_rows[:top_n], test_start, test_end, horizon, prediction_key) | {
        "model": model,
        "train_end": train_end,
        "test_start": test_start,
        "test_end": test_end,
        "top_n": top_n,
    }


def evaluate_rows(
    con: sqlite3.Connection,
    season: str,
    all_rows: list[dict],
    rows: list[dict],
    test_start: int,
    test_end: int,
    horizon: int,
    prediction_key: str = "next_6_xppg",
) -> dict:
    all_actual = [future_points(con, season, row["player_id"], test_start, test_end) for row in all_rows]
    quartile_cutoff = sorted(all_actual, reverse=True)[max(0, len(all_actual) // 4 - 1)] if all_actual else 0
    errors = []
    excess = []
    hits = 0
    top_quartile_hits = 0
    for row in rows:
        actual = future_points(con, season, row["player_id"], test_start, test_end)
        predicted = row[prediction_key] * horizon
        par = row["value_par"] * horizon
        errors.append(predicted - actual)
        excess.append(actual - par)
        hits += actual > par
        top_quartile_hits += actual >= quartile_cutoff
    return {
        "players": len(rows),
        "mae": round(mae(errors), 2),
        "rmse": round(rmse(errors), 2),
        "spearman": round(spearman([row[prediction_key] for row in all_rows], all_actual), 2),
        "avg_excess_points": round(sum(excess) / len(excess), 2) if excess else 0.0,
        "beating_par_rate": round(hits / len(rows), 2) if rows else 0.0,
        "top_quartile_hit_rate": round(top_quartile_hits / len(rows), 2) if rows else 0.0,
    }


def walk_forward(con: sqlite3.Connection, season: str = "2025-26", par_season: str = "2026-27") -> list[dict]:
    results = []
    for _, train_end, test_start, test_end in WINDOWS:
        for top_n in (10, 20):
            results.append(evaluate_model(con, season, par_season, train_end, test_start, test_end, top_n, "naive_ppg", "actual_ppg", "actual_ppg"))
            results.append(evaluate_model(con, season, par_season, train_end, test_start, test_end, top_n, "buy_delta", "buy_delta_6"))
            results.append(evaluate_model(con, season, par_season, train_end, test_start, test_end, top_n, "opportunity", "opportunity_score"))
            results.append(evaluate_model(con, season, par_season, train_end, test_start, test_end, top_n, "captain", "captain_adjusted_delta"))
    return results
