import argparse

from backend.data.db import connect
from backend.services.alerts import generate_tracked_alerts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2026-27")
    args = parser.parse_args()
    with connect() as con:
        count = generate_tracked_alerts(con, args.season)
    print(f"generated {count} alerts")


if __name__ == "__main__":
    main()
