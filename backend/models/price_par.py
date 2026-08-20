from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.models.config import ModelConfig, POSITIONS


@dataclass(frozen=True)
class ParPoint:
    position: str
    price: float
    market_mean: float
    value_par: float
    sample_size: int
    confidence: str


def weighted_quantile(values, weights, quantile: float) -> float:
    frame = pd.DataFrame({"value": values, "weight": weights}).sort_values("value")
    cutoff = frame["weight"].sum() * quantile
    return float(frame.loc[frame["weight"].cumsum() >= cutoff, "value"].iloc[0])


def pava(y: list[float], w: list[float]) -> list[float]:
    blocks: list[tuple[float, float, int]] = []
    for value, weight in zip(y, w):
        blocks.append((value, weight, 1))
        while len(blocks) >= 2 and blocks[-2][0] > blocks[-1][0]:
            v1, w1, n1 = blocks.pop()
            v0, w0, n0 = blocks.pop()
            blocks.append(((v0 * w0 + v1 * w1) / (w0 + w1), w0 + w1, n0 + n1))
    return [value for value, _, count in blocks for _ in range(count)]


def confidence_for(sample_size: int, price: float, observed_prices: list[float], config: ModelConfig) -> str:
    if not observed_prices:
        return "LOW"
    extrapolated = price < min(observed_prices) or price > max(observed_prices)
    if extrapolated or sample_size < 3:
        return "LOW"
    if sample_size < 6:
        return "MEDIUM"
    return "HIGH"


def build_historical_curves(players: pd.DataFrame, config: ModelConfig = ModelConfig()) -> list[ParPoint]:
    required = {"element_type", "now_cost", "total_points", "minutes"}
    missing = required - set(players.columns)
    if missing:
        raise ValueError(f"missing columns: {', '.join(sorted(missing))}")

    df = players.copy()
    df["position"] = df["element_type"].map(POSITIONS).fillna(df["element_type"])
    df["price"] = pd.to_numeric(df["now_cost"], errors="coerce") / 10
    df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce").fillna(0)
    df["total_points"] = pd.to_numeric(df["total_points"], errors="coerce").fillna(0)
    df = df[(df["minutes"] >= config.historical_min_minutes) & df["price"].notna()].copy()
    df["points_per_team_gameweek"] = df["total_points"] / 38
    df["points_per_90"] = df["total_points"] / df["minutes"] * 90

    points: list[ParPoint] = []
    for position, group in df.groupby("position"):
        grouped = (
            group.groupby("price")
            .apply(
                lambda g: pd.Series(
                    {
                        "market_mean": g["points_per_team_gameweek"].mean(),
                        "value_par": weighted_quantile(
                            g["points_per_team_gameweek"],
                            g["minutes"],
                            config.value_par_percentile,
                        ),
                        "sample_size": len(g),
                    }
                ),
                include_groups=False,
            )
            .reset_index()
            .sort_values("price")
        )
        if grouped.empty:
            continue
        weights = grouped["sample_size"].astype(float).clip(lower=1).tolist()
        grouped["market_mean"] = pava(grouped["market_mean"].tolist(), weights)
        grouped["value_par"] = pava(grouped["value_par"].tolist(), weights)
        observed = grouped["price"].tolist()
        for row in grouped.itertuples(index=False):
            points.append(
                ParPoint(
                    position=position,
                    price=float(row.price),
                    market_mean=round(float(row.market_mean), 3),
                    value_par=round(float(row.value_par), 3),
                    sample_size=int(row.sample_size),
                    confidence=confidence_for(int(row.sample_size), float(row.price), observed, config),
                )
            )
    return points


def interpolate(points: list[ParPoint], position: str, price: float) -> tuple[float, float, str]:
    curve = sorted([p for p in points if p.position == position], key=lambda p: p.price)
    if not curve:
        raise ValueError(f"no curve for {position}")
    if price <= curve[0].price:
        p = curve[0]
        return p.market_mean, p.value_par, "LOW"
    if price >= curve[-1].price:
        p = curve[-1]
        return p.market_mean, p.value_par, "LOW"
    for left, right in zip(curve, curve[1:]):
        if left.price <= price <= right.price:
            span = right.price - left.price
            ratio = 0 if span == 0 else (price - left.price) / span
            market = left.market_mean + ratio * (right.market_mean - left.market_mean)
            par = left.value_par + ratio * (right.value_par - left.value_par)
            confidence = "LOW" if "LOW" in {left.confidence, right.confidence} else "MEDIUM"
            return round(market, 3), round(par, 3), confidence
    raise AssertionError("unreachable")
