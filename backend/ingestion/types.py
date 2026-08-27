from __future__ import annotations

from typing import NotRequired, TypeAlias, TypedDict

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class ShotContext(TypedDict):
    player: str
    team: str
    opponent: str
    match: str | int | None
    minute: int
    xg: float
    x_coordinate: float
    y_coordinate: float
    result: str | None
    situation: str | None
    player_assisted: str | None
    shots_in_box: bool
    high_quality_chance: bool


class FixtureContext(TypedDict):
    fixture_id: int
    gameweek: int | None
    home_team_id: int
    away_team_id: int
    kickoff_time: str | None
    home_score: int | None
    away_score: int | None
    home_difficulty: int | None
    away_difficulty: int | None
    finished: bool
    started: bool


class TeamContext(TypedDict):
    team_id: int
    team_name: str
    team_short_name: str
    team_xg: float
    team_xga: float
    team_xg_last_5: float
    team_xga_last_5: float
    team_shots_conceded: int
    team_high_quality_chances_conceded: int
    strength_attack_home: int | None
    strength_attack_away: int | None
    strength_defence_home: int | None
    strength_defence_away: int | None
    blank_gw: NotRequired[list[int]]
    double_gw: NotRequired[list[int]]
    next_5_fixtures: NotRequired[list[dict[str, JsonValue]]]


class PlayerContext(TypedDict, total=False):
    player_id: int
    player_name: str
    team_id: int
    team_name: str
    position: str
    current_price: float | None
    next_5_fixtures: list[dict[str, JsonValue]]


class ManagerContext(TypedDict, total=False):
    manager_id: int
    context_type: str
    current_squad: list[int]
    purchase_prices: dict[int, float | None]
    selling_prices: dict[int, float | None]
    bank: float | None
    team_value: float | None
    free_transfers: int | None
    chips_remaining: list[str]


class FplContext(TypedDict):
    players: list[PlayerContext]
    teams: list[TeamContext]
    fixtures: list[FixtureContext]
    manager: ManagerContext
    shots: list[ShotContext]
    current_gw: int | None
    next_gw: int | None
    gw_deadline: str | None
