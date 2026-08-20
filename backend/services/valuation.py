def player_status(next_6_delta: float, next_3_delta: float, confidence: float, actual_delta: float = 0.0) -> str:
    if next_6_delta >= 0.75 and next_3_delta >= 0.35 and confidence >= 0.75:
        return "STRONG BUY"
    if next_6_delta >= 0.35 and confidence >= 0.5:
        return "BUY"
    if next_6_delta >= 0.1:
        return "WATCH"
    if actual_delta > 0.5 and next_6_delta < 0:
        return "SELL HIGH"
    if next_6_delta <= -0.5:
        return "SELL"
    if next_6_delta < 0 and actual_delta > 0:
        return "AVOID"
    return "HOLD"


def selling_price(purchase_price: float, current_price: float) -> float:
    profit_tenths = round((current_price - purchase_price) * 10)
    if profit_tenths <= 0:
        return current_price
    return round(purchase_price + (profit_tenths // 2) / 10, 1)


def transfer_verdict(gain: float) -> str:
    if gain < 2:
        return "ignore"
    if gain < 4:
        return "marginal"
    if gain < 6:
        return "interesting"
    return "strong"


def captaincy_weight(current_price: float) -> float:
    if current_price >= 12:
        return 0.6
    if current_price >= 10:
        return 0.35
    return 0.0


def captain_adjusted_delta(next_xppg: float, value_par: float, current_price: float) -> float:
    return next_xppg * (1 + captaincy_weight(current_price)) - value_par
