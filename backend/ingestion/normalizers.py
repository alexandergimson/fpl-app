from __future__ import annotations

from backend.ingestion.config import HIGH_QUALITY_XG_THRESHOLD, POSITIONS, understat_shot_in_box
from backend.ingestion.derived_metrics import minutes_per_game, net_transfers

CHIP_ALLOWANCES = {"wildcard": 2, "freehit": 1, "bboost": 1, "3xc": 1}


def price(value: int | float | str | None) -> float | None:
    return None if value is None else round(float(value) / 10, 1)


def decimal(value: int | float | str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def availability_percent(status: str | None, chance_next: int | None) -> int | None:
    if chance_next is not None:
        return int(chance_next)
    if status == "a":
        return 100
    return None


def normalise_player(raw: dict, teams: dict[int, dict], history: list[dict] | None = None, shot_summary: dict | None = None) -> dict:
    team_id = int(raw.get("team") or 0)
    team = teams.get(team_id, {})
    shots = shot_summary or {}
    return {
        "player_id": int(raw["id"]),
        "player_name": raw.get("web_name") or "",
        "team_id": team_id,
        "team_name": team.get("name") or raw.get("team_name") or "",
        "position": POSITIONS.get(int(raw.get("element_type") or 0), str(raw.get("element_type"))),
        "current_price": price(raw.get("now_cost")),
        "price_change_event": price(raw.get("cost_change_event")),
        "price_change_season": price(raw.get("cost_change_start")),
        "price_change_percent": decimal(raw.get("price_change_percent")),
        "price_change_hourly_rate": decimal(raw.get("price_change_hourly_rate")),
        "price_change_projections": raw.get("price_change_projections"),
        "price_change_locked_until": raw.get("price_change_locked_until"),
        "price_change_calibrating": raw.get("price_change_calibrating"),
        "selected_by_percent": decimal(raw.get("selected_by_percent")),
        "status": raw.get("status"),
        "chance_of_playing_this_round": raw.get("chance_of_playing_this_round"),
        "chance_of_playing_next_round": raw.get("chance_of_playing_next_round"),
        "availability_percent": availability_percent(raw.get("status"), raw.get("chance_of_playing_next_round")),
        "news": raw.get("news") or "",
        "total_minutes": int(raw.get("minutes") or 0),
        "starts": int(raw.get("starts") or 0),
        "minutes_per_game": minutes_per_game(history or []),
        "total_points": int(raw.get("total_points") or 0),
        "points_per_game": decimal(raw.get("points_per_game")),
        "form": decimal(raw.get("form")),
        "expected_points_this_gw": decimal(raw.get("ep_this")),
        "expected_points_next_gw": decimal(raw.get("ep_next")),
        "bps": int(raw.get("bps") or 0),
        "ict_index": decimal(raw.get("ict_index")),
        "influence": decimal(raw.get("influence")),
        "creativity": decimal(raw.get("creativity")),
        "threat": decimal(raw.get("threat")),
        "goals": int(raw.get("goals_scored") or 0),
        "assists": int(raw.get("assists") or 0),
        "expected_goals": decimal(raw.get("expected_goals")),
        "expected_assists": decimal(raw.get("expected_assists")),
        "expected_goal_involvements": decimal(raw.get("expected_goal_involvements")),
        "expected_goals_per_90": decimal(raw.get("expected_goals_per_90")),
        "expected_assists_per_90": decimal(raw.get("expected_assists_per_90")),
        "expected_goal_involvements_per_90": decimal(raw.get("expected_goal_involvements_per_90")),
        "shots": shots.get("shots", 0),
        "shots_in_box": shots.get("shots_in_box", 0),
        "high_quality_chances": shots.get("high_quality_chances", 0),
        "high_quality_chances_created": shots.get("high_quality_chances_created", 0),
        "key_passes": shots.get("key_passes", 0),
        "penalties_order": raw.get("penalties_order"),
        "direct_freekicks_order": raw.get("direct_freekicks_order"),
        "corners_and_indirect_freekicks_order": raw.get("corners_and_indirect_freekicks_order"),
        "clean_sheets": int(raw.get("clean_sheets") or 0),
        "goals_conceded": int(raw.get("goals_conceded") or 0),
        "saves": int(raw.get("saves") or 0),
        "penalties_saved": int(raw.get("penalties_saved") or 0),
        "expected_goals_conceded": decimal(raw.get("expected_goals_conceded")),
        "expected_goals_conceded_per_90": decimal(raw.get("expected_goals_conceded_per_90")),
        "defensive_contribution": decimal(raw.get("defensive_contribution")),
        "defensive_contribution_per_90": decimal(raw.get("defensive_contribution_per_90")),
        "transfers_in_event": int(raw.get("transfers_in_event") or 0),
        "transfers_out_event": int(raw.get("transfers_out_event") or 0),
        "net_transfers": net_transfers(raw.get("transfers_in_event"), raw.get("transfers_out_event")),
    }


def normalise_team(raw: dict, understat: dict | None = None) -> dict:
    extra = understat or {}
    return {
        "team_id": int(raw["id"]),
        "team_name": raw.get("name") or "",
        "team_short_name": raw.get("short_name") or "",
        "team_xg": extra.get("team_xg", 0.0),
        "team_xga": extra.get("team_xga", 0.0),
        "team_xg_last_5": extra.get("team_xg_last_5", 0.0),
        "team_xga_last_5": extra.get("team_xga_last_5", 0.0),
        "team_shots_conceded": extra.get("team_shots_conceded", 0),
        "team_high_quality_chances_conceded": extra.get("team_high_quality_chances_conceded", 0),
        "strength_attack_home": raw.get("strength_attack_home"),
        "strength_attack_away": raw.get("strength_attack_away"),
        "strength_defence_home": raw.get("strength_defence_home"),
        "strength_defence_away": raw.get("strength_defence_away"),
    }


def normalise_fixture(raw: dict) -> dict:
    return {
        "fixture_id": int(raw["id"]),
        "gameweek": raw.get("event"),
        "home_team_id": int(raw["team_h"]),
        "away_team_id": int(raw["team_a"]),
        "kickoff_time": raw.get("kickoff_time"),
        "home_score": raw.get("team_h_score"),
        "away_score": raw.get("team_a_score"),
        "home_difficulty": raw.get("team_h_difficulty"),
        "away_difficulty": raw.get("team_a_difficulty"),
        "finished": bool(raw.get("finished")),
        "started": bool(raw.get("started")),
    }


def normalise_manager(manager_id: int, entry: dict, picks: list[dict], transfers: list[dict], authenticated: bool = False, chip_history: list[dict] | None = None) -> dict:
    used: dict[str, int] = {}
    for row in chip_history or []:
        name = row.get("name") if isinstance(row, dict) else None
        if name:
            used[name] = used.get(name, 0) + 1
    chips_remaining = [name for name, allowed in CHIP_ALLOWANCES.items() for _ in range(max(0, allowed - used.get(name, 0)))]
    return {
        "manager_id": manager_id,
        "context_type": "authenticated" if authenticated else "public",
        "current_squad": [int(row["element"]) for row in picks],
        "purchase_prices": {int(row["element"]): price(row.get("purchase_price")) for row in picks if row.get("purchase_price") is not None} if authenticated else {},
        "selling_prices": {int(row["element"]): price(row.get("selling_price")) for row in picks if row.get("selling_price") is not None} if authenticated else {},
        "bank": price(entry.get("bank")) if authenticated else None,
        "team_value": price(entry.get("value")) if authenticated else None,
        "free_transfers": entry.get("free_transfers") if authenticated else None,
        "transfers_made_this_gw": entry.get("transfers"),
        "transfer_cost_this_gw": entry.get("event_transfers_cost"),
        "transfer_history": transfers,
        "captain": next((int(row["element"]) for row in picks if row.get("is_captain")), None),
        "vice_captain": next((int(row["element"]) for row in picks if row.get("is_vice_captain")), None),
        "chips_remaining": sorted(chips_remaining),
        "overall_rank": entry.get("overall_rank"),
        "current_gw": entry.get("current_event"),
        "next_gw": entry.get("next_event"),
        "gw_deadline": entry.get("deadline_time"),
    }


def normalise_shot(raw: dict, threshold: float = HIGH_QUALITY_XG_THRESHOLD) -> dict:
    xg = float(raw.get("xg") or raw.get("xG") or 0)
    x = float(raw.get("x_coordinate") or raw.get("X") or 0)
    y = float(raw.get("y_coordinate") or raw.get("Y") or 0)
    return {
        "player": raw.get("player") or raw.get("player_name") or "",
        "team": raw.get("team") or "",
        "opponent": raw.get("opponent") or "",
        "match": raw.get("match") or raw.get("match_id"),
        "minute": int(raw.get("minute") or 0),
        "xg": xg,
        "x_coordinate": x,
        "y_coordinate": y,
        "result": raw.get("result"),
        "situation": raw.get("situation"),
        "player_assisted": raw.get("player_assisted"),
        "shots_in_box": understat_shot_in_box(x, y),
        "high_quality_chance": xg >= threshold,
    }
