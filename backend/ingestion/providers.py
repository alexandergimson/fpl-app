from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import pandas as pd


RAW_BASE = "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data"
FPL_BOOTSTRAP = "https://fantasy.premierleague.com/api/bootstrap-static/"


@dataclass(frozen=True)
class Dataset:
    frame: pd.DataFrame
    source: str
    fetched_at: str
    data_period: str


class HistoricalProvider:
    def players(self, season: str) -> Dataset:
        raise NotImplementedError


class VaastavHistoricalProvider(HistoricalProvider):
    def __init__(self, cache_dir: Path = Path("backend/data/raw")):
        self.cache_dir = cache_dir

    def players(self, season: str) -> Dataset:
        url = f"{RAW_BASE}/{season}/players_raw.csv"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached = self.cache_dir / f"{season}-players_raw.csv"
        if cached.exists():
            return Dataset(pd.read_csv(cached), str(cached), datetime.fromtimestamp(cached.stat().st_mtime, timezone.utc).isoformat(), season)
        with urlopen(url, timeout=30) as response:
            cached.write_bytes(response.read())
        return Dataset(pd.read_csv(cached), url, datetime.now(timezone.utc).isoformat(), season)


class OfficialFplProvider:
    def bootstrap(self, season: str = "2026-27") -> Dataset:
        with urlopen(FPL_BOOTSTRAP, timeout=30) as response:
            data = pd.read_json(response)
        return Dataset(data, FPL_BOOTSTRAP, datetime.now(timezone.utc).isoformat(), season)
