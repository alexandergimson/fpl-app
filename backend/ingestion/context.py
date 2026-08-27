from __future__ import annotations

from backend.ingestion.derived_metrics import blank_gameweeks, double_gameweeks, shot_summaries
from backend.ingestion.normalizers import normalise_fixture, normalise_manager, normalise_player, normalise_shot, normalise_team
from backend.ingestion.providers import OfficialFplProvider, UnderstatProvider
from backend.ingestion.types import FplContext


def team_understat_summary(rows: list[dict]) -> dict[int, dict]:
    result: dict[int, dict] = {}
    by_team: dict[int, list[dict]] = {}
    for row in rows:
        by_team.setdefault(int(row["team_id"]), []).append(row)
    for team_id, team_rows in by_team.items():
        ordered = sorted(team_rows, key=lambda item: int(item.get("gameweek") or 0))
        last_5 = ordered[-5:]
        result[team_id] = {
            "team_xg": round(sum(float(row.get("xg") or 0) for row in ordered), 2),
            "team_xga": round(sum(float(row.get("xga") or 0) for row in ordered), 2),
            "team_xg_last_5": round(sum(float(row.get("xg") or 0) for row in last_5), 2),
            "team_xga_last_5": round(sum(float(row.get("xga") or 0) for row in last_5), 2),
        }
    return result


def next_fixtures(team_id: int, fixtures: list[dict], teams: dict[int, dict], start_gw: int | None, limit: int = 5) -> list[dict]:
    upcoming = []
    for fixture in fixtures:
        gw = fixture.get("event")
        if gw is None or (start_gw is not None and int(gw) < start_gw):
            continue
        is_home = int(fixture["team_h"]) == team_id
        is_away = int(fixture["team_a"]) == team_id
        if not (is_home or is_away):
            continue
        opponent_id = int(fixture["team_a"] if is_home else fixture["team_h"])
        opponent = teams.get(opponent_id, {})
        upcoming.append(
            {
                "gameweek": int(gw),
                "opponent_team_id": opponent_id,
                "opponent": opponent.get("short_name") or opponent.get("name"),
                "home_away": "H" if is_home else "A",
                "fdr": fixture.get("team_h_difficulty") if is_home else fixture.get("team_a_difficulty"),
                "opponent_attacking_strength": opponent.get("strength_attack_away") if is_home else opponent.get("strength_attack_home"),
                "opponent_defensive_strength": opponent.get("strength_defence_away") if is_home else opponent.get("strength_defence_home"),
            }
        )
    return sorted(upcoming, key=lambda item: (item["gameweek"], item["opponent_team_id"]))[:limit]


def build_fpl_context(
    manager_id: int,
    season: str = "2026-27",
    fpl_provider: OfficialFplProvider | None = None,
    understat_provider: UnderstatProvider | None = None,
    authenticated: bool = False,
) -> FplContext:
    fpl = fpl_provider or OfficialFplProvider()
    understat = understat_provider or UnderstatProvider()
    bootstrap = fpl.bootstrap(season)
    fixtures_dataset = fpl.fixtures(season)
    elements = bootstrap.frame.to_dict("records")
    teams_frame = bootstrap.frame.attrs.get("teams")
    teams_raw = teams_frame.to_dict("records")
    fixtures_raw = fixtures_dataset.frame.to_dict("records")
    current_gw = int(bootstrap.frame.attrs.get("current_gameweek") or 0)
    next_gw = bootstrap.frame.attrs.get("next_gameweek")
    gw_deadline = bootstrap.frame.attrs.get("next_deadline")
    if authenticated:
        picks_dataset = fpl.my_team(manager_id, season)
        entry = picks_dataset.frame.attrs.get("transfers", {})
    else:
        picks_dataset = fpl.entry_picks(manager_id, current_gw or 1, season)
        entry = picks_dataset.frame.attrs.get("entry_history", {})
    transfers = fpl.entry_transfers(manager_id, season).frame.to_dict("records") if hasattr(fpl, "entry_transfers") else []
    shots = [normalise_shot(row) for row in understat.shots(season).frame.to_dict("records")]
    shot_by_player, shot_by_team = shot_summaries(shots)
    team_underlying = team_understat_summary(understat.team_underlying(season, teams_frame, fixtures_dataset.frame).frame.to_dict("records"))
    teams_by_id = {int(row["id"]): row for row in teams_raw}
    teams = []
    for row in teams_raw:
        team_id = int(row["id"])
        team = normalise_team(row, team_underlying.get(team_id, {}) | shot_by_team.get(row.get("name") or "", {}))
        team["next_5_fixtures"] = next_fixtures(team_id, fixtures_raw, teams_by_id, next_gw or current_gw or None)
        teams.append(team)
    history_by_player: dict[int, list[dict]] = {}
    for player_id in [int(row["element"]) for row in picks_dataset.frame.to_dict("records") if row.get("element") is not None]:
        history_by_player[player_id] = fpl.element_summary(player_id, season).frame.to_dict("records") if hasattr(fpl, "element_summary") else []
    players = []
    for row in elements:
        player = normalise_player(row, teams_by_id, history_by_player.get(int(row["id"]), []), shot_by_player.get(row.get("web_name") or ""))
        player["next_5_fixtures"] = next_fixtures(player["team_id"], fixtures_raw, teams_by_id, next_gw or current_gw or None)
        players.append(player)
    fixtures = [normalise_fixture(row) for row in fixtures_raw]
    team_ids = [team["team_id"] for team in teams]
    gameweeks = sorted({int(row["gameweek"]) for row in fixtures if row.get("gameweek") is not None})
    blanks = blank_gameweeks(fixtures_raw, team_ids, gameweeks)
    doubles = double_gameweeks(fixtures_raw, team_ids, gameweeks)
    for team in teams:
        team["blank_gw"] = blanks.get(team["team_id"], [])
        team["double_gw"] = doubles.get(team["team_id"], [])
    return {
        "players": players,
        "teams": teams,
        "fixtures": fixtures,
        "manager": normalise_manager(manager_id, entry, picks_dataset.frame.to_dict("records"), transfers, authenticated),
        "shots": shots,
        "current_gw": current_gw or None,
        "next_gw": next_gw,
        "gw_deadline": gw_deadline,
    }


buildFplContext = build_fpl_context
