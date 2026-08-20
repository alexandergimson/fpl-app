from backend.data.db import connect


WINDOWS = [(1, 5, 6, 10), (1, 10, 11, 16), (1, 15, 16, 21), (1, 20, 21, 26)]


def main() -> None:
    with connect() as con:
        count = con.execute("SELECT COUNT(*) AS n FROM players").fetchone()["n"]
    print("walk-forward windows:", WINDOWS)
    print(f"players loaded: {count}")
    print("backtest v1 scaffold: leakage guard is window definitions; GW performance ingestion is next.")


if __name__ == "__main__":
    main()
