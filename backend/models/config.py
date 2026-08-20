from dataclasses import dataclass


POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


@dataclass(frozen=True)
class ModelConfig:
    historical_min_minutes: int = 2000
    value_par_percentile: float = 0.75
    extrapolation_buffer_m: float = 0.5
    transfer_ignore_points: float = 2.0
    transfer_interesting_points: float = 4.0
    transfer_strong_points: float = 6.0
    buy_delta_strong: float = 0.75
    buy_delta_buy: float = 0.35
    buy_delta_watch: float = 0.1
    sell_delta: float = -0.5
    confidence_high: float = 0.75
    confidence_medium: float = 0.5


CURRENT_BLEND_WEIGHTS = [
    (1, 3, 0.90, 0.10),
    (4, 6, 0.75, 0.25),
    (7, 10, 0.55, 0.45),
    (11, 15, 0.35, 0.65),
    (16, 38, 0.20, 0.80),
]


def prior_weight_for_gw(gameweek: int) -> tuple[float, float]:
    for start, end, historical, current in CURRENT_BLEND_WEIGHTS:
        if start <= gameweek <= end:
            return historical, current
    return CURRENT_BLEND_WEIGHTS[-1][2:]
