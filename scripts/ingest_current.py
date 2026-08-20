import argparse

from backend.data.db import connect
from backend.ingestion.loaders import upsert_players
from backend.ingestion.providers import OfficialFplProvider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2026-27")
    args = parser.parse_args()

    dataset = OfficialFplProvider().bootstrap(args.season)
    with connect() as con:
        count = upsert_players(con, args.season, dataset.frame, dataset.source, dataset.fetched_at)
    gameweek = dataset.frame.attrs.get("current_gameweek", 0)
    print(f"ingested {count} current players from official FPL API; finished GW={gameweek}")


if __name__ == "__main__":
    main()
