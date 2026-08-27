from __future__ import annotations

import sqlite3

from backend.services.valuation import selling_price


SQUAD_HEALTH = {
    "strong": "STRONG",
    "healthy": "HEALTHY",
    "watch": "WATCH",
    "review": "REVIEW",
}


def upsert_squad_player(
    con: sqlite3.Connection,
    season: str,
    player_id: int,
    purchase_price: float,
    current_price: float | None = None,
) -> None:
    if current_price is None:
        row = con.execute(
            "SELECT current_price FROM players WHERE season = ? AND player_id = ?",
            (season, player_id),
        ).fetchone()
        current_price = row["current_price"] if row else purchase_price
    con.execute(
        """
        INSERT OR REPLACE INTO squad_players (season, player_id, purchase_price, current_price, selling_price)
        VALUES (?, ?, ?, ?, ?)
        """,
        (season, player_id, purchase_price, current_price, selling_price(purchase_price, current_price)),
    )
    con.commit()


def remove_squad_player(con: sqlite3.Connection, season: str, player_id: int) -> None:
    con.execute("DELETE FROM squad_players WHERE season = ? AND player_id = ?", (season, player_id))
    con.commit()


def squad_analysis(con: sqlite3.Connection, season: str, par_season: str = "2026-27", bank: float = 0.0) -> list[dict]:
    owned = con.execute(
        """
        SELECT
          m.player_id, m.player, m.team, m.position, m.current_price,
          m.actual_points, m.current_par AS value_par, m.return_delta,
          m.underlying_xppg, m.underlying_xppg AS process_xppg_regressed,
          m.performance_delta, m.performance_data_state, m.performance_confidence,
          m.next_6_xppg, m.forward_delta, m.expected_minutes, m.projection_confidence,
          m.value_trend, m.tracked, s.purchase_price, s.selling_price
        FROM squad_players s
        JOIN current_player_metrics m ON m.season = s.season AND m.player_id = s.player_id
        WHERE s.season = ?
        """,
        (season,),
    ).fetchall()
    result = []
    for row in owned:
        player = dict(row)
        result.append(
            player
            | {
                "squad_health": squad_health(player["forward_delta"], player["expected_minutes"], player["projection_confidence"], player["value_trend"]),
            }
        )
    return sorted(result, key=lambda item: item["forward_delta"])


def squad_health(forward_delta: float, expected_minutes: float, confidence: float, value_trend: float) -> str:
    if forward_delta <= -0.5 and confidence >= 0.55:
        return SQUAD_HEALTH["review"]
    if forward_delta < -0.15 or expected_minutes < 55 or confidence < 0.45 or value_trend < -0.25:
        return SQUAD_HEALTH["watch"]
    if forward_delta >= 0.5 and expected_minutes >= 60 and confidence >= 0.55:
        return SQUAD_HEALTH["strong"]
    return SQUAD_HEALTH["healthy"]


def latest_public_gameweek(history_frame) -> int:
    if history_frame.empty or "event" not in history_frame:
        return 0
    return int(history_frame["event"].max())


def save_team_id(con: sqlite3.Connection, season: str, team_id: int) -> None:
    con.execute(
        """
        INSERT OR REPLACE INTO app_state (season, key, value)
        VALUES (?, 'fpl_team_id', ?)
        """,
        (season, str(team_id)),
    )
    con.commit()


def get_team_id(con: sqlite3.Connection, season: str) -> int | None:
    row = con.execute("SELECT value FROM app_state WHERE season = ? AND key = 'fpl_team_id'", (season,)).fetchone()
    return int(row["value"]) if row else None


def import_public_squad(con: sqlite3.Connection, season: str, team_id: int, provider) -> dict:
    history = provider.entry_history(team_id, season)
    gameweek = latest_public_gameweek(history.frame)
    if gameweek <= 0:
        save_team_id(con, season, team_id)
        return {"team_id": team_id, "gameweek": 0, "players": 0}
    picks = provider.entry_picks(team_id, gameweek, season)
    con.execute("DELETE FROM squad_players WHERE season = ?", (season,))
    for row in picks.frame.itertuples(index=False):
        player_id = int(row.element)
        price_row = con.execute("SELECT current_price FROM players WHERE season = ? AND player_id = ?", (season, player_id)).fetchone()
        price = float(price_row["current_price"]) if price_row else 0.0
        upsert_squad_player(con, season, player_id, price, price)
    save_team_id(con, season, team_id)
    return {"team_id": team_id, "gameweek": gameweek, "players": len(picks.frame)}
