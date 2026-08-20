import argparse

from backend.data.db import connect
from backend.services.tracking import snapshot_tracked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--par-season", default="2026-27")
    parser.add_argument("--gameweek", type=int)
    args = parser.parse_args()
    with connect() as con:
        count = snapshot_tracked(con, args.season, args.par_season, args.gameweek)
    print(f"snapshotted {count} tracked players")


if __name__ == "__main__":
    main()
