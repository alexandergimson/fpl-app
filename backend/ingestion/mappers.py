from __future__ import annotations

from backend.ingestion.providers import normalise_name


def map_understat_players(fpl_players: list[dict], understat_players: list[dict]) -> dict[str, int]:
    exact = {}
    for player in fpl_players:
        team = str(player.get("team_name") or player.get("team") or "")
        names = {
            str(player.get("player_name") or ""),
            str(player.get("web_name") or ""),
            f"{player.get('first_name') or ''} {player.get('second_name') or ''}".strip(),
        }
        for name in names:
            exact[(normalise_name(name), team)] = int(player["player_id"])
    result = {}
    for player in understat_players:
        key = (normalise_name(str(player.get("player_name") or player.get("player") or "")), str(player.get("team") or ""))
        mapped = exact.get(key)
        if mapped is not None:
            result[str(player.get("id") or player.get("provider_player_id") or player.get("player_name"))] = mapped
    return result
