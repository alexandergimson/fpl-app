from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import gzip
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request
from urllib.request import urlopen

import pandas as pd


RAW_BASE = "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data"
FPL_BOOTSTRAP = "https://fantasy.premierleague.com/api/bootstrap-static/"
FPL_FIXTURES = "https://fantasy.premierleague.com/api/fixtures/"
FPL_ENTRY_HISTORY = "https://fantasy.premierleague.com/api/entry/{team_id}/history/"
FPL_ENTRY_PICKS = "https://fantasy.premierleague.com/api/entry/{team_id}/event/{gameweek}/picks/"
UNDERSTAT_LEAGUE_DATA = "https://understat.com/getLeagueData/{league}/{year}"


@dataclass(frozen=True)
class Dataset:
    frame: pd.DataFrame
    source: str
    fetched_at: str
    data_period: str


class HistoricalProvider:
    def players(self, season: str) -> Dataset:
        raise NotImplementedError

    def gameweeks(self, season: str) -> Dataset:
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

    def gameweeks(self, season: str) -> Dataset:
        url = f"{RAW_BASE}/{season}/gws/merged_gw.csv"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached = self.cache_dir / f"{season}-merged_gw.csv"
        if cached.exists():
            return Dataset(pd.read_csv(cached), str(cached), datetime.fromtimestamp(cached.stat().st_mtime, timezone.utc).isoformat(), season)
        with urlopen(url, timeout=60) as response:
            cached.write_bytes(response.read())
        return Dataset(pd.read_csv(cached), url, datetime.now(timezone.utc).isoformat(), season)


class OfficialFplProvider:
    def __init__(self, cache_dir: Path = Path("backend/data/raw")):
        self.cache_dir = cache_dir

    def _json(self, url: str, cache_name: str):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached = self.cache_dir / cache_name
        try:
            with urlopen(url, timeout=60) as response:
                payload = json.load(response)
            cached.write_text(json.dumps(payload))
            return payload, url, datetime.now(timezone.utc).isoformat()
        except Exception:
            if cached.exists():
                return json.loads(cached.read_text()), str(cached), datetime.fromtimestamp(cached.stat().st_mtime, timezone.utc).isoformat()
            raise

    def bootstrap(self, season: str = "2026-27") -> Dataset:
        payload, source, fetched_at = self._json(FPL_BOOTSTRAP, f"{season}-bootstrap.json")
        elements = pd.DataFrame(payload["elements"])
        teams = pd.DataFrame(payload["teams"])
        events = pd.DataFrame(payload["events"])
        elements.attrs["teams"] = teams
        elements.attrs["current_gameweek"] = int(events.loc[events["finished"], "id"].max()) if events["finished"].any() else 0
        return Dataset(elements, source, fetched_at, season)

    def fixtures(self, season: str = "2026-27") -> Dataset:
        payload, source, fetched_at = self._json(FPL_FIXTURES, f"{season}-fixtures.json")
        return Dataset(pd.DataFrame(payload), source, fetched_at, season)

    def entry_history(self, team_id: int, season: str = "2026-27") -> Dataset:
        url = FPL_ENTRY_HISTORY.format(team_id=team_id)
        payload, source, fetched_at = self._json(url, f"{season}-entry-{team_id}-history.json")
        return Dataset(pd.DataFrame(payload.get("current", [])), source, fetched_at, season)

    def entry_picks(self, team_id: int, gameweek: int, season: str = "2026-27") -> Dataset:
        url = FPL_ENTRY_PICKS.format(team_id=team_id, gameweek=gameweek)
        payload, source, fetched_at = self._json(url, f"{season}-entry-{team_id}-gw-{gameweek}-picks.json")
        picks = pd.DataFrame(payload.get("picks", []))
        picks.attrs["entry_history"] = payload.get("entry_history", {})
        return Dataset(picks, source, fetched_at, season)


UNDERSTAT_TEAM_ALIASES = {
    "Manchester City": "Man City",
    "Manchester United": "Man Utd",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nott'm Forest",
    "Tottenham": "Spurs",
    "Tottenham Hotspur": "Spurs",
}


class UnderstatProvider:
    def __init__(self, cache_dir: Path = Path("backend/data/raw"), league: str = "EPL"):
        self.cache_dir = cache_dir
        self.league = league

    def _json(self, season: str):
        year = season_year(season)
        url = UNDERSTAT_LEAGUE_DATA.format(league=self.league, year=year)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached = self.cache_dir / f"{season}-understat-league.json"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "Referer": f"https://understat.com/league/{self.league}/{year}",
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            payload = json.loads(raw.decode("utf-8"))
            cached.write_text(json.dumps(payload))
            return payload, url, datetime.now(timezone.utc).isoformat()
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            if cached.exists():
                return json.loads(cached.read_text()), str(cached), datetime.fromtimestamp(cached.stat().st_mtime, timezone.utc).isoformat()
            raise

    def team_underlying(self, season: str, teams: pd.DataFrame, fixtures: pd.DataFrame) -> Dataset:
        payload, source, fetched_at = self._json(season)
        team_ids = fpl_team_ids(teams)
        fixtures_by_team_date = fixture_gameweeks_by_team_date(fixtures)
        rows = []
        for team in payload.get("teams", {}).values():
            team_id = team_ids.get(UNDERSTAT_TEAM_ALIASES.get(team["title"], team["title"]))
            if not team_id:
                continue
            for match in team.get("history", []):
                gameweek = fixtures_by_team_date.get((team_id, str(match.get("date", ""))[:10]))
                if not gameweek:
                    continue
                rows.append(
                    {
                        "team_id": team_id,
                        "gameweek": gameweek,
                        "is_home": 1 if match.get("h_a") == "h" else 0,
                        "xg": float(match.get("xG") or 0),
                        "xga": float(match.get("xGA") or 0),
                    }
                )
        return Dataset(pd.DataFrame(rows), source, fetched_at, season)


def season_year(season: str) -> int:
    match = re.match(r"^(\d{4})", season)
    if not match:
        raise ValueError(f"invalid season: {season}")
    return int(match.group(1))


def fpl_team_ids(teams: pd.DataFrame) -> dict[str, int]:
    return {str(row["name"]): int(row["id"]) for row in teams.to_dict("records")}


def fixture_gameweeks_by_team_date(fixtures: pd.DataFrame) -> dict[tuple[int, str], int]:
    result = {}
    if fixtures.empty:
        return result
    for row in fixtures.to_dict("records"):
        gameweek = row.get("event")
        kickoff = row.get("kickoff_time")
        if pd.isna(gameweek) or not kickoff:
            continue
        date = str(kickoff)[:10]
        result[(int(row["team_h"]), date)] = int(gameweek)
        result[(int(row["team_a"]), date)] = int(gameweek)
    return result
