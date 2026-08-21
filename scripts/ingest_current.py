import argparse

from backend.data.db import connect
from backend.ingestion.loaders import replace_fixtures, replace_fpl_player_underlying, set_state, snapshot_prices, upsert_players
from backend.ingestion.providers import OfficialFplProvider
from backend.services.ingestion_runs import add_health_event, finish_ingestion_run, start_ingestion_run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2026-27")
    args = parser.parse_args()

    provider = OfficialFplProvider()
    with connect() as con:
        run_id = start_ingestion_run(con, args.season, "official_fpl", "current")
    try:
        dataset = provider.bootstrap(args.season)
        fixtures = provider.fixtures(args.season)
        with connect() as con:
            count = upsert_players(con, args.season, dataset.frame, dataset.source, dataset.fetched_at)
            price_count = snapshot_prices(con, args.season, dataset.frame, dataset.source, dataset.fetched_at)
            underlying_count = replace_fpl_player_underlying(con, args.season, dataset.frame, dataset.fetched_at)
            fixture_count = replace_fixtures(con, args.season, fixtures.frame, fixtures.source, fixtures.fetched_at)
            set_state(con, args.season, "current_gameweek", str(dataset.frame.attrs.get("current_gameweek", 0)))
            if count < 500:
                add_health_event(con, args.season, run_id, "WARN", "player_count", f"Only {count} players received")
            if fixture_count < 300:
                add_health_event(con, args.season, run_id, "WARN", "fixture_count", f"Only {fixture_count} fixtures received")
            summary = f"{count} current players, {price_count} prices, {fixture_count} fixtures, {underlying_count} FPL xG/xA rows"
            finish_ingestion_run(con, run_id, "SUCCESS", summary)
    except Exception as exc:
        with connect() as con:
            finish_ingestion_run(con, run_id, "FAILED", str(exc))
            add_health_event(con, args.season, run_id, "ERROR", "provider_error", str(exc))
        raise
    gameweek = dataset.frame.attrs.get("current_gameweek", 0)
    print(f"ingested {count} current players, {price_count} prices, {fixture_count} fixtures and {underlying_count} FPL xG/xA rows from official FPL API; finished GW={gameweek}")


if __name__ == "__main__":
    main()
