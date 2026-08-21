import argparse

from backend.jobs.refresh import refresh_all


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--par-season", default="2026-27")
    args = parser.parse_args()
    result = refresh_all(args.season, args.par_season)
    print(
        "refresh SUCCESS: "
        f"GW={result['gameweek']}, "
        f"players={result['players']}, "
        f"prices={result['prices']}, "
        f"fixtures={result['fixtures']}, "
        f"fpl_xg_xa={result['underlying']}, "
        f"squad={result['squad']}, "
        f"snapshots={result['snapshots']}, "
        f"alerts={result['alerts']}"
    )


if __name__ == "__main__":
    main()
