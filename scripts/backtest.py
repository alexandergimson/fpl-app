from backend.data.db import connect
from backend.backtests.metrics import WINDOWS, walk_forward


def main() -> None:
    with connect() as con:
        count = con.execute("SELECT COUNT(*) AS n FROM players").fetchone()["n"]
        results = walk_forward(con) if count else []
    print("walk-forward windows:", WINDOWS)
    print(f"players loaded: {count}")
    print("model       train_end test_window top_n players mae rmse spear avg_excess hit_rate par_cov top_q")
    for row in results:
        print(
            f"{row['model']:<11} "
            f"GW{row['train_end']:<2} "
            f"GW{row['test_start']}-{row['test_end']} "
            f"{row['top_n']:<5} "
            f"{row['players']:<7} "
            f"{row['mae']:<4.2f} "
            f"{row['rmse']:<5.2f} "
            f"{row['spearman']:<5.2f} "
            f"{row['avg_excess_points']:+.2f} "
            f"{row['beating_par_rate']:.2f} "
            f"{row['frozen_par_coverage']:.2f} "
            f"{row['top_quartile_hit_rate']:.2f}"
        )
    print("backtest: naive PPG vs Buy Delta, Opportunity Score and Captain-adjusted ranking.")


if __name__ == "__main__":
    main()
