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
    team_xg: float | None
    team_xga: float | None
    team_xg_last_5: float | None
    team_xga_last_5: float | None
    team_shots_conceded: int | None
    team_high_quality_chances_conceded: int | None
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
    price_change_event: float | None
    price_change_season: float | None
    price_change_percent: float | None
    price_change_hourly_rate: float | None
    price_change_projections: JsonValue
    price_change_locked_until: JsonValue
    price_change_calibrating: JsonValue
    selected_by_percent: float | None
    status: str | None
    chance_of_playing_this_round: int | None
    chance_of_playing_next_round: int | None
    availability_percent: int | None
    news: str
    total_minutes: int
    starts: int
    minutes_per_game: float | None
    total_points: int
    points_per_game: float | None
    form: float | None
    expected_points_this_gw: float | None
    expected_points_next_gw: float | None
    bps: int
    ict_index: float | None
    influence: float | None
    creativity: float | None
    threat: float | None
    goals: int
    assists: int
    expected_goals: float | None
    expected_assists: float | None
    expected_goal_involvements: float | None
    expected_goals_per_90: float | None
    expected_assists_per_90: float | None
    expected_goal_involvements_per_90: float | None
    shots: int | None
    shots_in_box: int | None
    high_quality_chances: int | None
    high_quality_chances_created: int | None
    key_passes: int | None
    penalties_order: JsonValue
    direct_freekicks_order: JsonValue
    corners_and_indirect_freekicks_order: JsonValue
    clean_sheets: int
    goals_conceded: int
    saves: int
    penalties_saved: int
    expected_goals_conceded: float | None
    expected_goals_conceded_per_90: float | None
    defensive_contribution: float | None
    defensive_contribution_per_90: float | None
    transfers_in_event: int
    transfers_out_event: int
    net_transfers: int
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
    chips_remaining: list[str] | None


class FplContext(TypedDict):
    players: list[PlayerContext]
    teams: list[TeamContext]
    fixtures: list[FixtureContext]
    manager: ManagerContext
    shots: list[ShotContext]
    current_gw: int | None
    next_gw: int | None
    gw_deadline: str | None
