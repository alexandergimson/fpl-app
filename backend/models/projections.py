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


def confidence_label(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.5:
        return "MEDIUM"
    return "LOW"
