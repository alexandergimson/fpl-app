from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import gzip
import html
import json
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request
from urllib.request import urlopen

import pandas as pd


RAW_BASE = "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data"
FPL_BOOTSTRAP = "https://fantasy.premierleague.com/api/bootstrap-static/"
FPL_FIXTURES = "https://fantasy.premierleague.com/api/fixtures/"
FPL_ENTRY_HISTORY = "https://fantasy.premierleague.com/api/entry/{team_id}/history/"
FPL_ENTRY_PICKS = "https://fantasy.premierleague.com/api/entry/{team_id}/event/{gameweek}/picks/"
FPL_ELEMENT_SUMMARY = "https://fantasy.premierleague.com/api/element-summary/{player_id}/"
FPL_ENTRY = "https://fantasy.premierleague.com/api/entry/{team_id}/"
FPL_ENTRY_TRANSFERS = "https://fantasy.premierleague.com/api/entry/{team_id}/transfers/"
FPL_MY_TEAM = "https://fantasy.premierleague.com/api/my-team/{team_id}/"
UNDERSTAT_LEAGUE_DATA = "https://understat.com/getLeagueData/{league}/{year}"
UNDERSTAT_MATCH = "https://understat.com/match/{match_id}"
UNDERSTAT_MATCH_DATA = "https://understat.com/getMatchData/{match_id}"


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

    def element_summary(self, player_id: int, season: str = "2026-27") -> Dataset:
        payload, source, fetched_at = self._json(FPL_ELEMENT_SUMMARY.format(player_id=player_id), f"{season}-element-summary-{player_id}.json")
        history = pd.DataFrame(payload.get("history", []))
        history.attrs["fixtures"] = payload.get("fixtures", [])
        return Dataset(history, source, fetched_at, season)

    def entry(self, team_id: int, season: str = "2026-27") -> Dataset:
        payload, source, fetched_at = self._json(FPL_ENTRY.format(team_id=team_id), f"{season}-entry-{team_id}.json")
        return Dataset(pd.DataFrame([payload]), source, fetched_at, season)

    def bootstrap(self, season: str = "2026-27") -> Dataset:
        payload, source, fetched_at = self._json(FPL_BOOTSTRAP, f"{season}-bootstrap.json")
        elements = pd.DataFrame(payload["elements"])
        teams = pd.DataFrame(payload["teams"])
        events = pd.DataFrame(payload["events"])
        elements.attrs["teams"] = teams
        elements.attrs["events"] = events
        current = events.loc[events["is_current"], "id"] if "is_current" in events else pd.Series(dtype=int)
        next_event = events.loc[events["is_next"], "id"] if "is_next" in events else pd.Series(dtype=int)
        deadline = events.loc[events["is_next"], "deadline_time"] if "is_next" in events and "deadline_time" in events else pd.Series(dtype=str)
        elements.attrs["current_gameweek"] = int(current.iloc[0]) if not current.empty else 0
        elements.attrs["next_gameweek"] = int(next_event.iloc[0]) if not next_event.empty else None
        elements.attrs["next_deadline"] = str(deadline.iloc[0]) if not deadline.empty else None
        return Dataset(elements, source, fetched_at, season)

    def fixtures(self, season: str = "2026-27") -> Dataset:
        payload, source, fetched_at = self._json(FPL_FIXTURES, f"{season}-fixtures.json")
        return Dataset(pd.DataFrame(payload), source, fetched_at, season)

    def entry_history(self, team_id: int, season: str = "2026-27") -> Dataset:
        url = FPL_ENTRY_HISTORY.format(team_id=team_id)
        payload, source, fetched_at = self._json(url, f"{season}-entry-{team_id}-history.json")
        history = pd.DataFrame(payload.get("current", []))
        history.attrs["chips"] = payload.get("chips", [])
        history.attrs["past"] = payload.get("past", [])
        return Dataset(history, source, fetched_at, season)

    def entry_picks(self, team_id: int, gameweek: int, season: str = "2026-27") -> Dataset:
        url = FPL_ENTRY_PICKS.format(team_id=team_id, gameweek=gameweek)
        payload, source, fetched_at = self._json(url, f"{season}-entry-{team_id}-gw-{gameweek}-picks.json")
        picks = pd.DataFrame(payload.get("picks", []))
        picks.attrs["entry_history"] = payload.get("entry_history", {})
        return Dataset(picks, source, fetched_at, season)

    def entry_transfers(self, team_id: int, season: str = "2026-27") -> Dataset:
        payload, source, fetched_at = self._json(FPL_ENTRY_TRANSFERS.format(team_id=team_id), f"{season}-entry-{team_id}-transfers.json")
        return Dataset(pd.DataFrame(payload), source, fetched_at, season)

    def my_team(self, team_id: int, season: str = "2026-27") -> Dataset:
        payload, source, fetched_at = self._json(FPL_MY_TEAM.format(team_id=team_id), f"{season}-my-team-{team_id}.json")
        picks = pd.DataFrame(payload.get("picks", []))
        picks.attrs["transfers"] = payload.get("transfers", {})
        return Dataset(picks, source, fetched_at, season)


UNDERSTAT_TEAM_ALIASES = {
    "Coventry": "Coventry City",
    "Hull": "Hull City",
    "Ipswich": "Ipswich Town",
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

    def _match_json(self, match_id: str):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached = self.cache_dir / f"understat-match-{match_id}.json"
        if cached.exists():
            payload = json.loads(cached.read_text())
            return payload.get("shots", payload), str(cached), datetime.fromtimestamp(cached.stat().st_mtime, timezone.utc).isoformat()
        url = UNDERSTAT_MATCH_DATA.format(match_id=match_id)
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "Referer": UNDERSTAT_MATCH.format(match_id=match_id),
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        with urlopen(request, timeout=60) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
        payload = json.loads(raw.decode("utf-8"))
        cached.write_text(json.dumps(payload))
        return payload.get("shots", payload), url, datetime.now(timezone.utc).isoformat()

    def shots(self, season: str) -> Dataset:
        payload, source, fetched_at = self._json(season)
        rows = []
        for match in payload.get("dates", []):
            if not match.get("isResult"):
                continue
            match_id = str(match.get("id"))
            home = match.get("h", {}).get("title") or ""
            away = match.get("a", {}).get("title") or ""
            shots, source, fetched_at = self._match_json(match_id)
            for side, team, opponent in (("h", home, away), ("a", away, home)):
                for shot in shots.get(side, []):
                    rows.append(
                        {
                            "player": shot.get("player") or "",
                            "team": UNDERSTAT_TEAM_ALIASES.get(team, team),
                            "opponent": UNDERSTAT_TEAM_ALIASES.get(opponent, opponent),
                            "match": match_id,
                            "match_date": str(match.get("datetime") or "")[:10],
                            "minute": int(shot.get("minute") or 0),
                            "xG": float(shot.get("xG") or 0),
                            "X": float(shot.get("X") or 0),
                            "Y": float(shot.get("Y") or 0),
                            "result": shot.get("result"),
                            "situation": shot.get("situation"),
                            "player_assisted": shot.get("player_assisted"),
                        }
                    )
        return Dataset(pd.DataFrame(rows), source, fetched_at, season)

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

    def player_underlying(self, season: str, teams: pd.DataFrame, fixtures: pd.DataFrame) -> Dataset:
        """Research-only season-cumulative player feed; production refresh must not call this."""
        payload, source, fetched_at = self._json(season)
        fixtures_by_date = {str(row.get("kickoff_time", ""))[:10]: int(row["event"]) for row in fixtures.to_dict("records") if pd.notna(row.get("event")) and row.get("kickoff_time")}
        result_dates = [str(match.get("datetime", ""))[:10] for match in payload.get("dates", []) if match.get("isResult")]
        latest_date = max(result_dates, default="")
        latest_gw = fixtures_by_date.get(latest_date)
        rows = []
        for player in payload.get("players", []):
            if not player:
                continue
            rows.append(
                {
                    "provider_player_id": str(player.get("id")),
                    "player_name": player.get("player_name") or "",
                    "team": UNDERSTAT_TEAM_ALIASES.get(player.get("team_title") or "", player.get("team_title") or ""),
                    "match_date": latest_date,
                    "gameweek": latest_gw,
                    "minutes": int(float(player.get("time") or 0)),
                    "xg": float(player.get("xG") or 0),
                    "xa": float(player.get("xA") or 0),
                    "shots": int(float(player.get("shots") or 0)),
                    "key_passes": int(float(player.get("key_passes") or 0)),
                    "position": player.get("position"),
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


def normalise_name(value: str) -> str:
    folded = unicodedata.normalize("NFKD", html.unescape(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


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
