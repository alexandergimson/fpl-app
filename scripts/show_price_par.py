import argparse

from backend.data.db import connect
from backend.models.price_par import ParPoint, interpolate


SANITY_PRICES = {
    "DEF": [4.5, 5.0, 5.5, 6.0],
    "MID": [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0],
    "FWD": [6.0, 6.5, 7.5, 8.0, 9.0],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2026-27")
    args = parser.parse_args()
    with connect() as con:
        rows = con.execute(
            """
            SELECT position, price, market_mean, value_par, sample_size, confidence
            FROM price_par_points
            WHERE season = ?
            ORDER BY position, price
            """,
            (args.season,),
        ).fetchall()
    current = None
    for row in rows:
        if row["position"] != current:
            current = row["position"]
            print(f"\n{current}")
            print("price  mean  par75  n  conf")
        print(f"{row['price']:>4.1f}  {row['market_mean']:>4.2f}  {row['value_par']:>5.2f}  {row['sample_size']:>1}  {row['confidence']}")
    points = [
        ParPoint(row["position"], row["price"], row["market_mean"], row["value_par"], row["sample_size"], row["confidence"])
        for row in rows
    ]
    print("\nSanity points")
    print("pos price mean par75 conf")
    for position, prices in SANITY_PRICES.items():
        for price in prices:
            mean, par, confidence = interpolate(points, position, price)
            print(f"{position:>3} {price:>4.1f} {mean:>4.2f} {par:>5.2f} {confidence}")


if __name__ == "__main__":
    main()
