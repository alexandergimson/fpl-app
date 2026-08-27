from __future__ import annotations

from backend.ingestion.derived_metrics import blank_gameweeks, double_gameweeks, shot_summaries
from backend.ingestion.normalizers import normalise_fixture, normalise_manager, normalise_player, normalise_shot, normalise_team
from backend.ingestion.providers import OfficialFplProvider, UnderstatProvider


def build_fpl_context(manager_id: int, season: str = "2026-27", fpl_provider: OfficialFplProvider | None = None, understat_provider: UnderstatProvider | None = None) -> dict:
    fpl = fpl_provider or OfficialFplProvider()
    understat = understat_provider or UnderstatProvider()
    bootstrap = fpl.bootstrap(season)
    fixtures_dataset = fpl.fixtures(season)
    elements = bootstrap.frame.to_dict("records")
    teams_raw = bootstrap.frame.attrs.get("teams").to_dict("records")
    fixtures_raw = fixtures_dataset.frame.to_dict("records")
    current_gw = int(bootstrap.frame.attrs.get("current_gameweek") or 0)
    picks_dataset = fpl.entry_picks(manager_id, current_gw or 1, season)
    entry = picks_dataset.frame.attrs.get("entry_history", {})
    transfers = fpl.entry_transfers(manager_id, season).frame.to_dict("records") if hasattr(fpl, "entry_transfers") else []
    shots = [normalise_shot(row) for row in understat.shots(season).frame.to_dict("records")] if hasattr(understat, "shots") else []
    shot_by_player, shot_by_team = shot_summaries(shots)
    teams_by_id = {int(row["id"]): row for row in teams_raw}
    teams = [normalise_team(row, shot_by_team.get(row.get("name") or "")) for row in teams_raw]
    history_by_player: dict[int, list[dict]] = {}
    for player in elements:
        if hasattr(fpl, "element_summary"):
            history_by_player[int(player["id"])] = fpl.element_summary(int(player["id"]), season).frame.to_dict("records")
    players = [normalise_player(row, teams_by_id, history_by_player.get(int(row["id"]), []), shot_by_player.get(row.get("web_name") or "")) for row in elements]
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
        "manager": normalise_manager(manager_id, entry, picks_dataset.frame.to_dict("records"), transfers),
        "shots": shots,
    }


buildFplContext = build_fpl_context
