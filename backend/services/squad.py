from __future__ import annotations

import sqlite3

from backend.services.boards import buy_board
from backend.services.valuation import selling_price, transfer_verdict


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
    board = buy_board(con, season, par_season, None, 2000)
    by_id = {row["player_id"]: row for row in board}
    owned = con.execute("SELECT * FROM squad_players WHERE season = ?", (season,)).fetchall()
    result = []
    owned_ids = {row["player_id"] for row in owned}
    for row in owned:
        player = by_id.get(row["player_id"])
        if not player:
            continue
        budget = row["selling_price"] + bank
        replacements = [
            candidate
            for candidate in board
            if candidate["player_id"] not in owned_ids
            and candidate["position"] == player["position"]
            and candidate["current_price"] <= budget
        ]
        replacement = replacements[0] if replacements else None
        gain = (replacement["next_6_xppg"] - player["next_6_xppg"]) * 6 if replacement else 0.0
        hold_delta = player["next_6_xppg"] - player["market_mean"]
        result.append(
            player
            | {
                "purchase_price": row["purchase_price"],
                "selling_price": row["selling_price"],
                "hold_delta": round(hold_delta, 2),
                "best_replacement": replacement["player"] if replacement else None,
                "best_replacement_id": replacement["player_id"] if replacement else None,
                "transfer_gain": round(gain, 2),
                "transfer_verdict": transfer_verdict(gain),
                "squad_verdict": squad_verdict(hold_delta, gain),
            }
        )
    return sorted(result, key=lambda item: item["transfer_gain"], reverse=True)


def squad_verdict(hold_delta: float, transfer_gain: float) -> str:
    if transfer_gain >= 6:
        return "SELL"
    if transfer_gain >= 4:
        return "WATCH"
    if hold_delta >= 0:
        return "HOLD"
    if transfer_gain >= 2:
        return "WATCH"
    return "HOLD"
