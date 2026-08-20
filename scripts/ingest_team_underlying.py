import argparse
from datetime import datetime, timezone

import pandas as pd

from backend.data.db import connect
from backend.ingestion.loaders import replace_team_underlying


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--source", default="manual_csv")
    args = parser.parse_args()
    metrics = pd.read_csv(args.csv_path)
    with connect() as con:
        count = replace_team_underlying(con, args.season, metrics, args.source, datetime.now(timezone.utc).isoformat())
    print(f"ingested {count} team underlying gameweeks from {args.csv_path}")


if __name__ == "__main__":
    main()
