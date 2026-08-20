from backend.data.db import connect


if __name__ == "__main__":
    with connect() as con:
        tables = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print("created:", ", ".join(row["name"] for row in tables))
