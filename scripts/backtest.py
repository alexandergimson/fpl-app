from backend.data.db import connect
from backend.services.boards import buy_board
from backend.services.history import future_points


WINDOWS = [(1, 5, 6, 10), (1, 10, 11, 16), (1, 15, 16, 21), (1, 20, 21, 26)]


def main() -> None:
    with connect() as con:
        count = con.execute("SELECT COUNT(*) AS n FROM players").fetchone()["n"]
        sample = buy_board(con, "2025-26", "2026-27", None, 10, as_of_gw=5) if count else []
    print("walk-forward windows:", WINDOWS)
    print(f"players loaded: {count}")
    print("top historical buy-board sanity after GW5:")
    for row in sample:
        future = future_points(con, "2025-26", row["player_id"], 6, 10)
        print(f"{row['player']} {row['position']} £{row['current_price']:.1f} delta={row['buy_delta_6']:+.2f} GW6-10={future}")
    print("backtest v1: rankings use only as-of gameweek totals; metrics come next.")


if __name__ == "__main__":
    main()
