import argparse

from backend.data.db import connect
from backend.ingestion.loaders import replace_price_par, upsert_players
from backend.ingestion.providers import VaastavHistoricalProvider
from backend.models.config import ModelConfig
from backend.models.price_par import build_historical_curves


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-season", default="2025-26")
    parser.add_argument("--target-season", default="2026-27")
    parser.add_argument("--min-minutes", type=int, default=2000)
    args = parser.parse_args()

    config = ModelConfig(historical_min_minutes=args.min_minutes)
    dataset = VaastavHistoricalProvider().players(args.source_season)
    points = build_historical_curves(dataset.frame, config)
    with connect() as con:
        player_count = upsert_players(con, args.source_season, dataset.frame, dataset.source, dataset.fetched_at)
        par_count = replace_price_par(
            con,
            args.target_season,
            args.source_season,
            points,
            args.min_minutes,
            dataset.source,
            dataset.fetched_at,
        )
    print(f"ingested {player_count} players and {par_count} par points from {dataset.source}")


if __name__ == "__main__":
    main()
