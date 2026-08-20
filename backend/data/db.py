import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "backend" / "data" / "fpl.sqlite"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS players (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  code INTEGER,
  web_name TEXT NOT NULL,
  first_name TEXT,
  second_name TEXT,
  team_id INTEGER,
  team TEXT,
  position TEXT NOT NULL,
  current_price REAL NOT NULL,
  total_points INTEGER NOT NULL DEFAULT 0,
  minutes INTEGER NOT NULL DEFAULT 0,
  ownership REAL,
  status TEXT,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (season, player_id)
);

CREATE TABLE IF NOT EXISTS price_par_points (
  season TEXT NOT NULL,
  source_season TEXT NOT NULL,
  position TEXT NOT NULL,
  price REAL NOT NULL,
  market_mean REAL NOT NULL,
  value_par REAL NOT NULL,
  sample_size INTEGER NOT NULL,
  min_minutes INTEGER NOT NULL,
  confidence TEXT NOT NULL,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (season, source_season, position, price)
);

CREATE TABLE IF NOT EXISTS price_history (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  gameweek INTEGER,
  observed_on TEXT NOT NULL,
  price REAL NOT NULL,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (season, player_id, observed_on)
);

CREATE TABLE IF NOT EXISTS tracked_players (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  tracked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  note TEXT,
  PRIMARY KEY (season, player_id)
);

CREATE TABLE IF NOT EXISTS tracked_snapshots (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  gameweek INTEGER NOT NULL,
  price REAL NOT NULL,
  market_mean REAL NOT NULL,
  value_par REAL NOT NULL,
  actual_ppg REAL NOT NULL,
  neutral_xppg REAL NOT NULL,
  next_3_xppg REAL NOT NULL,
  next_6_xppg REAL NOT NULL,
  buy_delta REAL NOT NULL,
  ownership REAL,
  start_probability REAL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (season, player_id, gameweek)
);

CREATE TABLE IF NOT EXISTS squad_players (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  purchase_price REAL NOT NULL,
  current_price REAL NOT NULL,
  selling_price REAL NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (season, player_id)
);

CREATE TABLE IF NOT EXISTS minutes_overrides (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  start_probability REAL NOT NULL,
  expected_minutes_if_starting REAL NOT NULL,
  substitute_probability REAL NOT NULL,
  expected_minutes_if_sub REAL NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  season TEXT NOT NULL,
  player_id INTEGER,
  kind TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  acknowledged_at TEXT
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con
