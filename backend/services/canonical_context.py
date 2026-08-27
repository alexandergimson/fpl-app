from __future__ import annotations

import json
import sqlite3

from backend.ingestion.types import FplContext


def materialize_canonical_context(con: sqlite3.Connection, season: str, context: FplContext) -> None:
    con.execute("DELETE FROM current_canonical_player_context WHERE season = ?", (season,))
    con.execute("DELETE FROM current_canonical_team_context WHERE season = ?", (season,))
    con.executemany(
        """
        INSERT INTO current_canonical_player_context (
          season, player_id, shots, shots_in_box, high_quality_chances,
          high_quality_chances_created, key_passes, next_5_fixtures_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                season,
                player["player_id"],
                player.get("shots", 0),
                player.get("shots_in_box", 0),
                player.get("high_quality_chances", 0),
                player.get("high_quality_chances_created", 0),
                player.get("key_passes", 0),
                json.dumps(player.get("next_5_fixtures", []), sort_keys=True),
            )
            for player in context["players"]
        ],
    )
    con.executemany(
        """
        INSERT INTO current_canonical_team_context (
          season, team_id, team_xg, team_xga, team_xg_last_5, team_xga_last_5,
          team_shots_conceded, team_high_quality_chances_conceded
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                season,
                team["team_id"],
                team.get("team_xg", 0),
                team.get("team_xga", 0),
                team.get("team_xg_last_5", 0),
                team.get("team_xga_last_5", 0),
                team.get("team_shots_conceded", 0),
                team.get("team_high_quality_chances_conceded", 0),
            )
            for team in context["teams"]
        ],
    )
    manager = context["manager"]
    con.execute(
        """
        INSERT OR REPLACE INTO current_canonical_manager_context (
          season, manager_id, context_type, bank, free_transfers, chips_remaining_json, deadline
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            season,
            manager.get("manager_id"),
            manager.get("context_type") or "public",
            manager.get("bank"),
            manager.get("free_transfers"),
            json.dumps(manager.get("chips_remaining", []), sort_keys=True),
            context.get("gw_deadline") or manager.get("gw_deadline"),
        ),
    )
    con.commit()


def manager_context(con: sqlite3.Connection, season: str) -> dict:
    row = con.execute("SELECT * FROM current_canonical_manager_context WHERE season = ?", (season,)).fetchone()
    if not row:
        return {"bank": None, "free_transfers": None, "chips_remaining": [], "deadline": None, "context_type": None}
    return {
        "bank": row["bank"],
        "free_transfers": row["free_transfers"],
        "chips_remaining": json.loads(row["chips_remaining_json"] or "[]"),
        "deadline": row["deadline"],
        "context_type": row["context_type"],
    }
