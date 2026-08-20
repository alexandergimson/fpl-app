from __future__ import annotations

from math import exp


def expected_minutes(
    start_probability: float,
    expected_minutes_if_starting: float,
    substitute_probability: float,
    expected_minutes_if_sub: float,
) -> float:
    return start_probability * expected_minutes_if_starting + substitute_probability * expected_minutes_if_sub


def clean_sheet_ev(expected_opponent_goals: float, points: int, probability_of_60: float) -> float:
    return exp(-expected_opponent_goals) * points * probability_of_60


def defcon_ev(threshold_probability: float) -> float:
    return max(0.0, min(1.0, threshold_probability)) * 2


def role_xppg(position: str, expected_minutes: float, role: dict | None) -> float:
    if not role:
        return 0.0
    minutes_share = max(0.0, min(1.0, expected_minutes / 90))
    goal_points = 6 if position in {"GK", "DEF"} else 5 if position == "MID" else 4
    penalty = role["penalties"] * 0.12 * goal_points
    free_kick = role["direct_free_kicks"] * 0.03 * goal_points
    assist = (role["corners"] + role["indirect_free_kicks"]) * 0.08 * 3
    return minutes_share * (penalty + free_kick + assist)


def confidence_label(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.5:
        return "MEDIUM"
    return "LOW"


def projection_breakdown(row: dict) -> dict[str, float]:
    minutes_share = max(0.0, min(1.0, row["expected_minutes"] / 90))
    appearance = min(2.0, 2.0 * minutes_share)
    clean_sheet = row.get("clean_sheet_xppg_6", 0.0)
    fixture = row["next_6_xppg"] - row["neutral_xppg"]
    defcon = row.get("defcon_xppg", 0.0)
    bonus = row.get("bonus_xppg", 0.0)
    saves = row.get("save_xppg", 0.0)
    remaining = row["neutral_xppg"] - appearance - clean_sheet - defcon - bonus - saves
    attacking = max(0.0, remaining * (0.75 if row["position"] != "GK" else 0.1))
    bonus_other = row["neutral_xppg"] - appearance - clean_sheet - defcon - bonus - saves - attacking
    return {
        "appearance_ev": round(appearance, 2),
        "attacking_ev": round(attacking, 2),
        "clean_sheet_ev": round(clean_sheet, 2),
        "defcon_ev": round(defcon, 2),
        "bonus_ev": round(bonus, 2),
        "save_ev": round(saves, 2),
        "bonus_other_ev": round(bonus_other, 2),
        "fixture_adjustment": round(fixture, 2),
        "fixture_xpts": round(row["next_6_xppg"], 2),
    }
