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
    player_attack_prior_minutes: int = 900
    team_defence_prior_matches: int = 6
    gk_save_prior_minutes: int = 900


PLAYER_ATTACK_PRIOR_MINUTES = ModelConfig().player_attack_prior_minutes
TEAM_DEFENCE_PRIOR_MATCHES = ModelConfig().team_defence_prior_matches
GK_SAVE_PRIOR_MINUTES = ModelConfig().gk_save_prior_minutes


CURRENT_BLEND_WEIGHTS = [
    (0, 0, 1.00, 0.00),
    (1, 3, 0.75, 0.25),
    (4, 6, 0.60, 0.40),
    (7, 10, 0.40, 0.60),
    (11, 15, 0.25, 0.75),
    (16, 38, 0.15, 0.85),
]


def prior_weight_for_gw(gameweek: int) -> tuple[float, float]:
    for start, end, historical, current in CURRENT_BLEND_WEIGHTS:
        if start <= gameweek <= end:
            return historical, current
    if gameweek < CURRENT_BLEND_WEIGHTS[0][0]:
        return CURRENT_BLEND_WEIGHTS[0][2:]
    return CURRENT_BLEND_WEIGHTS[-1][2:]
