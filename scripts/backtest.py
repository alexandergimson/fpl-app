from backend.data.db import connect
from backend.services.boards import buy_board


WINDOWS = [(1, 5, 6, 10), (1, 10, 11, 16), (1, 15, 16, 21), (1, 20, 21, 26)]


def main() -> None:
    with connect() as con:
        count = con.execute("SELECT COUNT(*) AS n FROM players").fetchone()["n"]
        sample = buy_board(con, "2025-26", "2026-27", 38, 10) if count else []
    print("walk-forward windows:", WINDOWS)
    print(f"players loaded: {count}")
    print("top historical buy-board sanity:")
    for row in sample:
        print(f"{row['player']} {row['position']} £{row['current_price']:.1f} delta={row['buy_delta_6']:+.2f}")
    print("backtest v1 scaffold: leakage guard is window definitions; GW performance ingestion is next.")


if __name__ == "__main__":
    main()
