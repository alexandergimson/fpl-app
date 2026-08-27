HIGH_QUALITY_XG_THRESHOLD = 0.35

POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def understat_shot_in_box(x: float, y: float) -> bool:
    return x >= 0.83 and 0.21 <= y <= 0.79
