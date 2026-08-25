import argparse

from backend.data.db import connect
from backend.services.tracking import snapshot_current_predictions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--par-season", default="2026-27")
    parser.add_argument("--gameweek", type=int)
    args = parser.parse_args()
    with connect() as con:
        count = snapshot_current_predictions(con, args.season, args.par_season, args.gameweek)
    print(f"snapshotted {count} current predictions")


if __name__ == "__main__":
    main()
