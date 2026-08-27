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

CREATE TABLE IF NOT EXISTS teams (
  season TEXT NOT NULL,
  team_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  short_name TEXT NOT NULL,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (season, team_id)
);

CREATE TABLE IF NOT EXISTS app_state (
  season TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (season, key)
);

CREATE TABLE IF NOT EXISTS fixtures (
  season TEXT NOT NULL,
  fixture_id INTEGER NOT NULL,
  gameweek INTEGER,
  kickoff_time TEXT,
  team_h INTEGER NOT NULL,
  team_a INTEGER NOT NULL,
  team_h_difficulty INTEGER NOT NULL,
  team_a_difficulty INTEGER NOT NULL,
  finished INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (season, fixture_id)
);

CREATE TABLE IF NOT EXISTS player_gameweeks (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  gameweek INTEGER NOT NULL,
  fixture_id INTEGER,
  opponent_team INTEGER,
  was_home INTEGER NOT NULL DEFAULT 0,
  total_points INTEGER NOT NULL DEFAULT 0,
  minutes INTEGER NOT NULL DEFAULT 0,
  starts INTEGER NOT NULL DEFAULT 0,
  goals_scored INTEGER NOT NULL DEFAULT 0,
  assists INTEGER NOT NULL DEFAULT 0,
  clean_sheets INTEGER NOT NULL DEFAULT 0,
  goals_conceded INTEGER NOT NULL DEFAULT 0,
  saves INTEGER NOT NULL DEFAULT 0,
  bonus INTEGER NOT NULL DEFAULT 0,
  bps INTEGER NOT NULL DEFAULT 0,
  selected INTEGER,
  transfers_in INTEGER,
  transfers_out INTEGER,
  value REAL,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (season, player_id, gameweek, fixture_id)
);

CREATE TABLE IF NOT EXISTS player_cumulative_observations (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  gameweek INTEGER NOT NULL,
  total_points INTEGER NOT NULL DEFAULT 0,
  minutes INTEGER NOT NULL DEFAULT 0,
  bps INTEGER NOT NULL DEFAULT 0,
  xg REAL NOT NULL DEFAULT 0,
  xa REAL NOT NULL DEFAULT 0,
  ownership REAL,
  current_price REAL,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (season, player_id, gameweek, source)
);

CREATE TABLE IF NOT EXISTS player_underlying_gameweeks (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  gameweek INTEGER NOT NULL,
  minutes INTEGER NOT NULL DEFAULT 0,
  xg REAL NOT NULL DEFAULT 0,
  xa REAL NOT NULL DEFAULT 0,
  xg_observed INTEGER NOT NULL DEFAULT 1,
  xa_observed INTEGER NOT NULL DEFAULT 1,
  shots INTEGER,
  shots_in_box INTEGER,
  big_chances INTEGER,
  cbit REAL,
  cbirt REAL,
  cbit_observed INTEGER NOT NULL DEFAULT 0,
  cbirt_observed INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (season, player_id, gameweek, source)
);

CREATE TABLE IF NOT EXISTS game_underlying_xpts (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  gameweek INTEGER NOT NULL,
  source TEXT NOT NULL,
  minutes INTEGER NOT NULL DEFAULT 0,
  appearance_ev REAL NOT NULL DEFAULT 0,
  goal_ev REAL NOT NULL DEFAULT 0,
  assist_ev REAL NOT NULL DEFAULT 0,
  clean_sheet_process_ev REAL NOT NULL DEFAULT 0,
  defcon_ev REAL NOT NULL DEFAULT 0,
  bonus_process_ev REAL NOT NULL DEFAULT 0,
  save_process_ev REAL NOT NULL DEFAULT 0,
  deduction_process_ev REAL NOT NULL DEFAULT 0,
  game_underlying_xpts REAL NOT NULL DEFAULT 0,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (season, player_id, gameweek, source)
);

CREATE TABLE IF NOT EXISTS team_underlying_gameweeks (
  season TEXT NOT NULL,
  team_id INTEGER NOT NULL,
  gameweek INTEGER NOT NULL,
  is_home INTEGER,
  xg REAL NOT NULL DEFAULT 0,
  xga REAL NOT NULL DEFAULT 0,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (season, team_id, gameweek, source)
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
  model_run_id INTEGER,
  price REAL NOT NULL,
  market_mean REAL NOT NULL,
  value_par REAL NOT NULL,
  value_balance REAL,
  return_delta REAL,
  performance_delta REAL,
  actual_ppg REAL NOT NULL,
  neutral_xppg REAL NOT NULL,
  next_3_xppg REAL NOT NULL,
  next_6_xppg REAL NOT NULL,
  buy_delta REAL NOT NULL,
  ownership REAL,
  start_probability REAL,
  expected_minutes REAL,
  projection_confidence REAL,
  fixture_factor_6 REAL,
  xg90 REAL,
  xa90 REAL,
  model_version TEXT,
  component_versions TEXT,
  data_cutoff TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (season, player_id, gameweek)
);

CREATE TABLE IF NOT EXISTS model_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  season TEXT NOT NULL,
  gameweek INTEGER,
  model_version TEXT NOT NULL,
  component_versions TEXT NOT NULL,
  data_cutoff TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS current_prediction_snapshots (
  model_run_id INTEGER NOT NULL,
  season TEXT NOT NULL,
  gameweek INTEGER NOT NULL,
  player_id INTEGER NOT NULL,
  prediction_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (model_run_id, player_id)
);

CREATE TABLE IF NOT EXISTS current_player_metrics (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  player TEXT NOT NULL,
  team TEXT,
  team_id INTEGER,
  position TEXT NOT NULL,
  current_price REAL NOT NULL,
  actual_points REAL,
  relevant_gameweek INTEGER,
  current_par REAL,
  return_par REAL,
  return_delta REAL,
  value_balance REAL,
  underlying_xppg REAL,
  performance_delta REAL,
  performance_data_state TEXT NOT NULL,
  performance_confidence TEXT,
  next_6_xppg REAL,
  forward_delta REAL,
  expected_minutes REAL,
  projection_confidence REAL,
  value_trend REAL,
  is_emerging INTEGER NOT NULL DEFAULT 0,
  is_regression_risk INTEGER NOT NULL DEFAULT 0,
  tracked INTEGER NOT NULL DEFAULT 0,
  model_run_id INTEGER,
  data_cutoff TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (season, player_id)
);

CREATE TABLE IF NOT EXISTS current_performance_lineage (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  performance_delta REAL,
  underlying_xppg REAL,
  current_par REAL,
  state TEXT NOT NULL,
  confidence TEXT,
  sample_gameweeks INTEGER,
  sample_minutes INTEGER,
  prior_source TEXT,
  prior_confidence TEXT,
  appearance REAL NOT NULL DEFAULT 0,
  goal REAL NOT NULL DEFAULT 0,
  assist REAL NOT NULL DEFAULT 0,
  clean_sheet REAL NOT NULL DEFAULT 0,
  defcon REAL NOT NULL DEFAULT 0,
  bonus REAL NOT NULL DEFAULT 0,
  saves REAL NOT NULL DEFAULT 0,
  deductions REAL NOT NULL DEFAULT 0,
  forward_available INTEGER NOT NULL DEFAULT 0,
  model_run_id INTEGER,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (season, player_id)
);

CREATE TABLE IF NOT EXISTS current_forward_lineage (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  gameweek INTEGER NOT NULL,
  fixture_id INTEGER NOT NULL DEFAULT 0,
  opponent TEXT,
  home_away TEXT,
  expected_minutes REAL,
  projected_xpts REAL,
  gameweek_total_xpts REAL,
  next_6_xppg REAL,
  current_par REAL,
  forward_delta REAL,
  model_run_id INTEGER,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (season, player_id, gameweek, fixture_id)
);

CREATE INDEX IF NOT EXISTS idx_current_player_metrics_forward ON current_player_metrics (season, position, forward_delta);
CREATE INDEX IF NOT EXISTS idx_current_player_metrics_performance ON current_player_metrics (season, position, performance_delta);
CREATE INDEX IF NOT EXISTS idx_current_player_metrics_price ON current_player_metrics (season, position, current_price, forward_delta);
CREATE INDEX IF NOT EXISTS idx_current_player_metrics_tracked ON current_player_metrics (season, tracked, forward_delta);

CREATE TABLE IF NOT EXISTS frozen_player_gameweek_par (
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  gameweek INTEGER NOT NULL,
  fixture_id INTEGER NOT NULL DEFAULT 0,
  price REAL NOT NULL,
  position TEXT NOT NULL,
  value_par REAL NOT NULL,
  par_model_version TEXT NOT NULL,
  source TEXT NOT NULL,
  source_version TEXT,
  data_cutoff TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (season, player_id, gameweek, fixture_id)
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

CREATE TABLE IF NOT EXISTS player_role_overrides (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  season TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  penalties REAL NOT NULL DEFAULT 0,
  direct_free_kicks REAL NOT NULL DEFAULT 0,
  corners REAL NOT NULL DEFAULT 0,
  indirect_free_kicks REAL NOT NULL DEFAULT 0,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  season TEXT NOT NULL,
  player_id INTEGER,
  kind TEXT NOT NULL,
  dedupe_key TEXT UNIQUE,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  acknowledged_at TEXT
);

CREATE TABLE IF NOT EXISTS data_ingestion_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  season TEXT NOT NULL,
  provider TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  summary TEXT
);

CREATE TABLE IF NOT EXISTS data_health_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  season TEXT NOT NULL,
  run_id INTEGER,
  level TEXT NOT NULL,
  kind TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS external_player_mappings (
  provider TEXT NOT NULL,
  season TEXT NOT NULL,
  external_player_id TEXT NOT NULL,
  external_player_name TEXT NOT NULL,
  external_team TEXT,
  fpl_player_id INTEGER,
  mapping_method TEXT NOT NULL,
  confidence REAL NOT NULL,
  verified_at TEXT NOT NULL,
  PRIMARY KEY (provider, season, external_player_id)
);

CREATE TABLE IF NOT EXISTS external_player_underlying_observations (
  provider TEXT NOT NULL,
  season TEXT NOT NULL,
  external_player_id TEXT NOT NULL,
  external_player_name TEXT NOT NULL,
  external_team TEXT,
  gameweek INTEGER,
  match_date TEXT,
  minutes INTEGER NOT NULL DEFAULT 0,
  xg REAL NOT NULL DEFAULT 0,
  xa REAL NOT NULL DEFAULT 0,
  shots INTEGER,
  key_passes INTEGER,
  position TEXT,
  mapped_player_id INTEGER,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (provider, season, external_player_id, gameweek)
);

CREATE TABLE IF NOT EXISTS understat_player_cumulative_observations (
  provider TEXT NOT NULL,
  season TEXT NOT NULL,
  external_player_id TEXT NOT NULL,
  external_player_name TEXT NOT NULL,
  external_team TEXT,
  as_of_gameweek INTEGER NOT NULL,
  season_cumulative_minutes INTEGER NOT NULL DEFAULT 0,
  season_cumulative_xg REAL NOT NULL DEFAULT 0,
  season_cumulative_xa REAL NOT NULL DEFAULT 0,
  season_cumulative_shots INTEGER NOT NULL DEFAULT 0,
  season_cumulative_key_passes INTEGER NOT NULL DEFAULT 0,
  mapped_player_id INTEGER,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (provider, season, external_player_id, as_of_gameweek)
);

CREATE TABLE IF NOT EXISTS understat_player_gameweek_observations (
  provider TEXT NOT NULL,
  season TEXT NOT NULL,
  external_player_id TEXT NOT NULL,
  external_player_name TEXT NOT NULL,
  external_team TEXT,
  gameweek INTEGER NOT NULL,
  match_date TEXT,
  gameweek_minutes INTEGER NOT NULL DEFAULT 0,
  gameweek_xg REAL NOT NULL DEFAULT 0,
  gameweek_xa REAL NOT NULL DEFAULT 0,
  gameweek_shots INTEGER NOT NULL DEFAULT 0,
  gameweek_key_passes INTEGER NOT NULL DEFAULT 0,
  position TEXT,
  mapped_player_id INTEGER,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  data_period TEXT NOT NULL,
  PRIMARY KEY (provider, season, external_player_id, gameweek)
);
"""


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    if path != ":memory:":
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 15000")
    con.executescript(SCHEMA)
    ensure_columns(
        con,
        "player_underlying_gameweeks",
        {
            "cbit": "REAL",
            "cbirt": "REAL",
            "xg_observed": "INTEGER NOT NULL DEFAULT 1",
            "xa_observed": "INTEGER NOT NULL DEFAULT 1",
            "cbit_observed": "INTEGER NOT NULL DEFAULT 0",
            "cbirt_observed": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    ensure_columns(con, "player_cumulative_observations", {"bps": "INTEGER NOT NULL DEFAULT 0"})
    ensure_columns(con, "game_underlying_xpts", {"deduction_process_ev": "REAL NOT NULL DEFAULT 0"})
    ensure_columns(
        con,
        "tracked_snapshots",
        {
            "model_run_id": "INTEGER",
            "value_balance": "REAL",
            "return_delta": "REAL",
            "performance_delta": "REAL",
            "expected_minutes": "REAL",
            "projection_confidence": "REAL",
            "fixture_factor_6": "REAL",
            "xg90": "REAL",
            "xa90": "REAL",
            "model_version": "TEXT",
            "component_versions": "TEXT",
            "data_cutoff": "TEXT",
        },
    )
    return con


def ensure_columns(con: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}
    for name, kind in columns.items():
        if name not in existing:
            try:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc):
                    raise
    con.commit()
