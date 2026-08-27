from __future__ import annotations

from collections import Counter, defaultdict

from backend.ingestion.config import HIGH_QUALITY_XG_THRESHOLD, understat_shot_in_box


def net_transfers(transfers_in: int | None, transfers_out: int | None) -> int:
    return int(transfers_in or 0) - int(transfers_out or 0)


def minutes_per_game(history: list[dict]) -> float | None:
    appearances = [int(row.get("minutes") or 0) for row in history if int(row.get("minutes") or 0) > 0]
    return round(sum(appearances) / len(appearances), 2) if appearances else None


def fixture_counts(fixtures: list[dict]) -> dict[tuple[int, int], int]:
    counts: Counter[tuple[int, int]] = Counter()
    for fixture in fixtures:
        gameweek = fixture.get("event")
        if gameweek is None:
            continue
        counts[(int(fixture["team_h"]), int(gameweek))] += 1
        counts[(int(fixture["team_a"]), int(gameweek))] += 1
    return dict(counts)


def blank_gameweeks(fixtures: list[dict], team_ids: list[int], gameweeks: list[int]) -> dict[int, list[int]]:
    counts = fixture_counts(fixtures)
    return {team_id: [gw for gw in gameweeks if counts.get((team_id, gw), 0) == 0] for team_id in team_ids}


def double_gameweeks(fixtures: list[dict], team_ids: list[int], gameweeks: list[int]) -> dict[int, list[int]]:
    counts = fixture_counts(fixtures)
    return {team_id: [gw for gw in gameweeks if counts.get((team_id, gw), 0) >= 2] for team_id in team_ids}


def shot_summaries(shots: list[dict], threshold: float = HIGH_QUALITY_XG_THRESHOLD) -> tuple[dict[str, dict], dict[str, dict]]:
    players: dict[str, dict] = defaultdict(lambda: {"shots": 0, "shots_in_box": 0, "high_quality_chances": 0, "key_passes": 0, "high_quality_chances_created": 0})
    teams: dict[str, dict] = defaultdict(lambda: {"team_shots_conceded": 0, "team_high_quality_chances_conceded": 0})
    for shot in shots:
        player = str(shot.get("player") or "")
        team = str(shot.get("team") or "")
        opponent = str(shot.get("opponent") or "")
        xg = float(shot.get("xg") or 0)
        x = float(shot.get("x_coordinate") or 0)
        y = float(shot.get("y_coordinate") or 0)
        players[player]["shots"] += 1
        players[player]["shots_in_box"] += int(understat_shot_in_box(x, y))
        players[player]["high_quality_chances"] += int(xg >= threshold)
        assister = str(shot.get("player_assisted") or "")
        if assister:
            players[assister]["key_passes"] += 1
            players[assister]["high_quality_chances_created"] += int(xg >= threshold)
        if team and opponent:
            teams[opponent]["team_shots_conceded"] += 1
            teams[opponent]["team_high_quality_chances_conceded"] += int(xg >= threshold)
    return dict(players), dict(teams)
