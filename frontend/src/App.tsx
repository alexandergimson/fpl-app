import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import "./style.css";

type ParPoint = { position: string; price: number; market_mean: number; value_par: number; sample_size: number; confidence: string };

type BoardRow = {
  player_id: number;
  player: string;
  team: string;
  position: string;
  current_price: number;
  actual_points?: number | null;
  market_mean: number;
  value_par: number;
  value_balance: number | null;
  actual_ppg: number | null;
  historical_delta: number | null;
  return_delta: number | null;
  neutral_xppg: number;
  underlying_xppg: number;
  process_xppg_regressed?: number | null;
  performance_delta: number | null;
  performance_data_state: "missing" | "partial" | "sufficient";
  performance_confidence: "LOW" | "MEDIUM" | "HIGH";
  performance_sample_gameweeks?: number;
  performance_sample_minutes?: number;
  performance_model_version?: string;
  prior_source?: "player_history" | "historical_position_price" | "historical_position" | "none" | null;
  prior_confidence?: "LOW" | "MEDIUM" | "HIGH" | null;
  prior_minutes?: number;
  prior_seasons?: string | null;
  fixture_projection?: { gameweek: number; total_xpts: number; fixtures: Record<string, number | string | boolean>[] }[];
  next_3_xppg: number;
  next_6_xppg: number;
  buy_delta_6: number;
  forward_delta: number;
  expected_minutes: number;
  start_probability: number;
  projection_confidence: number;
  minutes_confidence: string;
  value_trend: number;
  price_trend: number;
  ownership?: number | null;
  is_emerging: boolean;
  is_regression_risk: boolean;
  status: string;
  squad_health?: string;
  selling_price?: number;
  purchase_price?: number;
  delta_momentum?: number;
  tracking_status?: string;
  xg90?: number | null;
  xa90?: number | null;
  raw_xg?: number | null;
  raw_xa?: number | null;
  role_xppg: number;
  clean_sheet_xppg_6: number;
  defcon_xppg: number;
  bonus_xppg: number;
  save_xppg: number;
  expected_opponent_goals_6: number;
  fixture_factor_6?: number;
  captain_adjusted_delta?: number;
  opportunity_score?: number;
  penalties: number;
  direct_free_kicks: number;
  corners: number;
  indirect_free_kicks: number;
  role_override_reason?: string | null;
  minutes_override_reason?: string | null;
};

type PlayerDetail = {
  current: BoardRow;
  projection_breakdown: Record<string, number>;
  recent_gameweeks: { gameweek: number; total_points: number; minutes: number; value: number }[];
  minutes_history: { start_probability: number; expected_minutes_if_starting: number; substitute_probability: number; expected_minutes_if_sub: number; reason: string; created_at: string }[];
  role_history: { penalties: number; direct_free_kicks: number; corners: number; indirect_free_kicks: number; reason: string; created_at: string }[];
  tracked_snapshots: { gameweek: number; model_run_id?: number | null; buy_delta: number; price: number; return_delta?: number | null; performance_delta?: number | null; forward_delta?: number | null; value_balance?: number | null }[];
};

type Alert = { id: number; kind: string; message: string; created_at: string };
type PriceMovement = { player_id: number; player: string; team: string; position: string; first_price: number; latest_price: number; price_change: number; gameweek?: number | null };
type PlayersPage = { players: BoardRow[]; page: number; page_size: number; total: number; total_pages: number };
type PerformanceLineage = {
  player_id: number;
  performance_delta: number | null;
  underlying_xppg: number | null;
  value_par: number;
  state: string;
  confidence: string;
  sample_gameweeks?: number;
  sample_minutes?: number;
  prior: { source?: string | null; confidence?: string | null };
  components: Record<string, number>;
  available_observations: string[];
  missing_required_observations: string[];
  forward_available: boolean;
  note: string;
};
type ForwardLineage = {
  player_id: number;
  forward_delta: number;
  next_6_xppg: number;
  value_par: number;
  gameweeks: { gameweek: number; projected_points: number; fixtures: { opponent: string; home_away: string; expected_minutes: number; total_xpts: number }[] }[];
};
type DataStatus = {
  season: string;
  current_gameweek?: number | null;
  latest_ingestion_runs: { id: number; provider: string; kind: string; status: string; started_at: string; finished_at?: string | null; summary?: string | null }[];
  latest_health_events: { id: number; level: string; kind: string; message: string; created_at: string }[];
  health_summary: {
    fpl_last_updated?: string | null;
    advanced_stats_last_updated?: string | null;
    expected_player_count: number;
    received_player_count: number;
    expected_fixture_count: number;
    processed_fixture_count: number;
    player_underlying_rows: number;
    team_underlying_rows: number;
    performance_sufficient_players: number;
    performance_partial_players: number;
    performance_missing_players: number;
    performance_coverage_by_position?: Record<string, { missing: number; partial: number; sufficient: number }>;
    understat_team_rows?: number;
    understat_team_mapping_coverage?: number;
    understat_player_rows_fetched?: number;
    understat_player_rows_mapped?: number;
    understat_player_mapping_unresolved?: number;
    player_prior_coverage?: Record<string, number>;
    low_confidence_prior_players?: number;
    latest_fixture_projection_run?: Record<string, string> | null;
    latest_ingestion_status?: string | null;
    historical_prior_weight: number;
    current_season_weight: number;
  };
  sources: { key: string; label: string; rows: number; fetched_at?: string | null; data_period?: string | null }[];
};

type SortKey =
  | "current_price"
  | "actual_points"
  | "historical_delta"
  | "return_delta"
  | "value_par"
  | "neutral_xppg"
  | "underlying_xppg"
  | "performance_delta"
  | "next_3_xppg"
  | "next_6_xppg"
  | "forward_delta"
  | "expected_minutes"
  | "projection_confidence"
  | "ownership"
  | "value_trend"
  | "price_trend";

type SortOption = "BEST_VALUE" | "PERFORMANCE" | "CHEAPEST";

const API = "http://127.0.0.1:8000";
const SEASON = "2026-27";
const tooltipText = {
  actual_points: "Actual FPL points scored in the relevant Gameweek.",
  value_par: "Expected points for a good FPL pick at this player's price and position.",
  return_delta: "Actual points minus Par. Positive means the pick returned above its price benchmark.",
  underlying_xppg: "Estimated FPL points per Gameweek from the player's underlying process, independent of price.",
  performance_delta: "Underlying xPPG minus Par. Positive means the player's underlying performance is above the standard required by their price.",
  forward_delta: "Projected Next-6 xPPG minus Par. Positive means the player is projected to offer value at their current price.",
  value_balance: "Total actual FPL points gained or lost versus the frozen Par from each completed Gameweek.",
  neutral_xppg: "Fixture-neutral underlying PPG before future fixture adjustment.",
  next_3_xppg: "Projected PPG across the next 3 fixtures.",
  next_6_xppg: "Projected PPG across the next 6 fixtures.",
  expected_minutes: "Expected minutes per match used by the projection.",
  confidence: "Projection confidence from minutes security, data sample, role and availability.",
  value_trend: "Current Forward Delta minus the previous tracked snapshot delta when available.",
};

function HeaderHelp({ label, tip }: { label: string; tip: string }) {
  return <button className="header-help" type="button" title={tip} aria-label={`${label}: ${tip}`}>{label}</button>;
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" }) : "not loaded";
}

function trendLabel(value: number) {
  if (value > 0.15) return "↑ improving";
  if (value < -0.15) return "↓ deteriorating";
  return "→ stable";
}

function confidenceLabel(value: number) {
  if (value >= 0.7) return "HIGH";
  if (value >= 0.45) return "MEDIUM";
  return "LOW";
}

function metric(value: number | null | undefined, digits = 2) {
  return value == null ? "—" : value.toFixed(digits);
}

function signedMetric(value: number | null | undefined, digits = 2) {
  return value == null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function money(value: number | null | undefined) {
  return value == null ? "—" : `£${value.toFixed(1)}`;
}

function valueTone(value: number | null | undefined) {
  if (value == null) return "";
  return value >= 0 ? "positive" : "negative";
}

function fixtureOpponent(fixture: Record<string, number | string | boolean>) {
  return fixture.opponent ?? `#${fixture.opponent_team_id}`;
}

function performanceTitle(row: BoardRow) {
  const prior = row.prior_source === "player_history" ? `Player-history prior, ${row.prior_minutes ?? 0} prior minutes.` : row.prior_source === "historical_position_price" ? "Historical position-price prior." : row.prior_source === "historical_position" ? "Historical position prior." : "No prior.";
  const sample = `${row.performance_data_state} evidence from ${row.performance_sample_gameweeks ?? 0} GW, ${row.performance_sample_minutes ?? 0} minutes.`;
  return row.performance_delta == null ? `No numeric Performance Delta yet. ${sample} ${prior}` : `${sample} Process xPPG ${metric(row.process_xppg_regressed)}. ${prior}`;
}

function priorLabel(row: BoardRow) {
  if (row.prior_source === "player_history") return `Player prior (${row.prior_minutes ?? 0}m)`;
  if (row.prior_source === "historical_position_price") return "Position-price prior";
  if (row.prior_source === "historical_position") return "Position prior";
  return "No prior";
}

function DeltaPopover({
  row,
  kind,
  performanceCache,
  forwardCache,
  setPerformanceCache,
  setForwardCache,
  selectPlayer,
}: {
  row: BoardRow;
  kind: "performance" | "forward";
  performanceCache: Record<number, PerformanceLineage | "error" | "loading">;
  forwardCache: Record<number, ForwardLineage | "error" | "loading">;
  setPerformanceCache: React.Dispatch<React.SetStateAction<Record<number, PerformanceLineage | "error" | "loading">>>;
  setForwardCache: React.Dispatch<React.SetStateAction<Record<number, ForwardLineage | "error" | "loading">>>;
  selectPlayer: (row: BoardRow) => void;
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);
  const hoverTimer = useRef<number | null>(null);
  const isPerformance = kind === "performance";
  const cache = isPerformance ? performanceCache[row.player_id] : forwardCache[row.player_id];
  const value = isPerformance ? row.performance_delta : row.forward_delta;
  const label = `${isPerformance ? "Performance" : "Forward"} Delta for ${row.player}`;

  function load() {
    setOpen(true);
    if (cache) return;
    if (isPerformance) {
      setPerformanceCache((current) => ({ ...current, [row.player_id]: "loading" }));
      fetch(`${API}/players/${row.player_id}/performance-lineage?season=${SEASON}`)
        .then((response) => response.json())
        .then((lineage) => setPerformanceCache((current) => ({ ...current, [row.player_id]: lineage })))
        .catch(() => setPerformanceCache((current) => ({ ...current, [row.player_id]: "error" })));
    } else {
      setForwardCache((current) => ({ ...current, [row.player_id]: "loading" }));
      fetch(`${API}/players/${row.player_id}/forward-lineage?season=${SEASON}`)
        .then((response) => response.json())
        .then((lineage) => setForwardCache((current) => ({ ...current, [row.player_id]: lineage })))
        .catch(() => setForwardCache((current) => ({ ...current, [row.player_id]: "error" })));
    }
  }

  function scheduleLoad() {
    hoverTimer.current = window.setTimeout(load, 200);
  }

  function close() {
    if (hoverTimer.current) window.clearTimeout(hoverTimer.current);
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    function close(event: MouseEvent) {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <span className="delta-wrap" ref={wrapRef} onMouseLeave={close}>
      <button
        type="button"
        className={`delta-trigger ${valueTone(value)}`}
        aria-label={label}
        aria-expanded={open}
        onMouseEnter={scheduleLoad}
        onFocus={load}
        onClick={() => (open ? setOpen(false) : load())}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
      >
        {signedMetric(value)}
      </button>
      {open && (
        <span className="popover" role="dialog" aria-label={`${label} details`}>
          {cache === "loading" || !cache ? <span className="note">Loading details...</span> : cache === "error" ? <span className="note">{isPerformance ? "Performance details unavailable." : "Projection details unavailable."}</span> : isPerformance ? (
            <PerformancePopover lineage={cache as PerformanceLineage} />
          ) : (
            <ForwardPopover lineage={cache as ForwardLineage} onDetail={() => selectPlayer(row)} />
          )}
        </span>
      )}
    </span>
  );
}

function PerformancePopover({ lineage }: { lineage: PerformanceLineage }) {
  const labels: Record<string, [string, string]> = {
    appearance: ["Playing time", "Expected appearance points based on projected minutes."],
    goal: ["Goals", "Expected goal points based on underlying xG, position and minutes."],
    assist: ["Assists", "Expected assist points based on underlying xA and minutes."],
    clean_sheet: ["Clean sheets", "Expected clean-sheet points based on team defensive strength and playing time."],
    defcon: ["Defensive contributions", "Expected points from reaching FPL defensive-contribution thresholds."],
    bonus: ["Bonus", "Expected bonus points based on underlying BPS tendency, not actual match bonus."],
    saves: ["Saves", "Expected goalkeeper save points."],
    deductions: ["Deductions", "Expected negative points from modelled deductions."],
  };
  return (
    <>
      <div className="popover-grid"><span>Underlying xPPG</span><strong>{metric(lineage.underlying_xppg)}</strong><span>Current Par</span><strong>{metric(lineage.value_par)}</strong><span>Performance Δ</span><strong>{signedMetric(lineage.performance_delta)}</strong><span>State</span><strong>{lineage.state}</strong></div>
      <h4>Expected points breakdown</h4>
      {Object.entries(lineage.components).filter(([, value]) => value !== 0).map(([key, value]) => <div className="line" title={labels[key]?.[1]} key={key}><span>{labels[key]?.[0] ?? key}</span><strong>{metric(value)}</strong></div>)}
      <h4>Evidence</h4>
      <p>Estimate confidence: {lineage.confidence.toLowerCase()}</p>
      <p>{lineage.sample_gameweeks ?? 0} GW · {lineage.sample_minutes ?? 0} mins</p>
      <p>Available: {lineage.available_observations.length ? lineage.available_observations.join(", ") : "none"}</p>
      <p>{lineage.prior.source ? "Blended with " + lineage.prior.source.replace(/_/g, " ") : "No player prior available"}</p>
      {lineage.missing_required_observations.map((item) => <p className="note" key={item}>{item}</p>)}
      {lineage.performance_delta == null && lineage.forward_available && <p className="note">Forward projection can still use historical priors and future fixtures.</p>}
      <p className="note">{lineage.note}</p>
    </>
  );
}

function ForwardPopover({ lineage, onDetail }: { lineage: ForwardLineage; onDetail: () => void }) {
  return (
    <>
      <div className="popover-grid"><span>Next-6 xPPG</span><strong>{metric(lineage.next_6_xppg)}</strong><span>Current Par</span><strong>{metric(lineage.value_par)}</strong><span>Forward Δ</span><strong>{signedMetric(lineage.forward_delta)}</strong></div>
      <h4>Outlook</h4>
      {lineage.gameweeks.map((gw) => <div className="line" key={gw.gameweek}><span>GW{gw.gameweek} {gw.fixtures.length === 1 ? `${gw.fixtures[0].opponent} (${gw.fixtures[0].home_away})` : gw.fixtures.length ? "total" : "Blank"}</span><strong>{metric(gw.projected_points)}</strong></div>)}
      <button className="action" type="button" onClick={onDetail}>View detail</button>
    </>
  );
}

function SortButton({ label, sortKey, active, direction, onSort, title }: { label: string; sortKey: SortKey; active: boolean; direction: "asc" | "desc"; onSort: (key: SortKey) => void; title?: string }) {
  return (
    <button className="sort" title={title} onClick={() => onSort(sortKey)}>
      {label}{active ? (direction === "desc" ? " ↓" : " ↑") : ""}
    </button>
  );
}

export function App() {
  const [players, setPlayers] = useState<BoardRow[]>([]);
  const [points, setPoints] = useState<ParPoint[]>([]);
  const [playersPage, setPlayersPage] = useState<PlayersPage>({ players: [], page: 1, page_size: 15, total: 0, total_pages: 1 });
  const [playersLoading, setPlayersLoading] = useState(false);
  const [tracked, setTracked] = useState<BoardRow[]>([]);
  const [squad, setSquad] = useState<BoardRow[]>([]);
  const [detail, setDetail] = useState<PlayerDetail | null>(null);
  const [teamId, setTeamId] = useState("");
  const [teamMessage, setTeamMessage] = useState("");
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("ALL");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [confidence, setConfidence] = useState("ALL");
  const [trackedOnly, setTrackedOnly] = useState(false);
  const [quickFilter, setQuickFilter] = useState("ALL");
  const [squadPlayerId, setSquadPlayerId] = useState("");
  const [purchasePrice, setPurchasePrice] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("forward_delta");
  const [sortDirection, setSortDirection] = useState<"desc" | "asc">("desc");
  const [sortOption, setSortOption] = useState<SortOption>("BEST_VALUE");
  const [page, setPage] = useState(1);
  const [performanceLineage, setPerformanceLineage] = useState<Record<number, PerformanceLineage | "error" | "loading">>({});
  const [forwardLineage, setForwardLineage] = useState<Record<number, ForwardLineage | "error" | "loading">>({});
  const [roleForm, setRoleForm] = useState({ penalties: false, direct_free_kicks: false, corners: false, indirect_free_kicks: false, reason: "" });
  const [minutesForm, setMinutesForm] = useState({ start_probability: "0.8", expected_minutes_if_starting: "75", substitute_probability: "0.2", expected_minutes_if_sub: "20", reason: "" });

  function loadSquad() {
    fetch(`${API}/squad?season=${SEASON}`)
      .then((response) => response.json())
      .then(setSquad)
      .catch(() => setSquad([]));
  }

function loadData() {
  fetch(`${API}/price-par?season=${SEASON}`)
    .then((response) => response.json())
    .then(setPoints)
    .catch(() => setPoints([]));

  fetch(`${API}/tracked-players?season=${SEASON}`)
    .then((response) => response.json())
    .then(setTracked)
    .catch(() => setTracked([]));

  fetch(`${API}/settings?season=${SEASON}`)
    .then((response) => response.json())
    .then((settings) => setTeamId(settings.fpl_team_id?.toString() ?? ""))
    .catch(() => undefined);

  loadSquad();
}

  useEffect(loadData, []);

  useEffect(() => {
    const params = new URLSearchParams({
      season: SEASON,
      page: page.toString(),
      page_size: "15",
      sort: sortKey,
      direction: sortDirection,
      position,
      search,
      quick_filter: quickFilter,
      confidence,
    });
    if (minPrice) params.set("min_price", minPrice);
    if (maxPrice) params.set("max_price", maxPrice);
    if (trackedOnly) params.set("tracked", "true");
    setPlayersLoading(true);
    fetch(`${API}/all-players?${params}`)
      .then((response) => response.json())
      .then((result: PlayersPage) => {
        setPlayersPage(result);
        setPlayers(result.players);
      })
      .catch(() => {
        setPlayersPage({ players: [], page: 1, page_size: 15, total: 0, total_pages: 1 });
        setPlayers([]);
      })
      .finally(() => setPlayersLoading(false));
  }, [page, sortKey, sortDirection, position, minPrice, maxPrice, trackedOnly, search, quickFilter, confidence]);

  useEffect(() => {
    if (!detail?.current) return;
    setRoleForm({
      penalties: detail.current.penalties > 0,
      direct_free_kicks: detail.current.direct_free_kicks > 0,
      corners: detail.current.corners > 0,
      indirect_free_kicks: detail.current.indirect_free_kicks > 0,
      reason: detail.current.role_override_reason ?? "",
    });
    const latestMinutes = detail.minutes_history[0];
    setMinutesForm({
      start_probability: (latestMinutes?.start_probability ?? detail.current.start_probability ?? 0.8).toString(),
      expected_minutes_if_starting: (latestMinutes?.expected_minutes_if_starting ?? Math.max(detail.current.expected_minutes, 60)).toString(),
      substitute_probability: (latestMinutes?.substitute_probability ?? 0.2).toString(),
      expected_minutes_if_sub: (latestMinutes?.expected_minutes_if_sub ?? 20).toString(),
      reason: detail.current.minutes_override_reason ?? latestMinutes?.reason ?? "",
    });
  }, [detail]);

  const trackedIds = useMemo(() => new Set(tracked.map((row) => row.player_id)), [tracked]);
  const squadIds = useMemo(() => new Set(squad.map((row) => row.player_id)), [squad]);
  const positions = ["ALL", "GK", "DEF", "MID", "FWD"];
  const squadSummary = useMemo(() => {
    const counts = { STRONG: 0, HEALTHY: 0, WATCH: 0, REVIEW: 0 };
    squad.forEach((row) => counts[row.squad_health as keyof typeof counts]++);
    const squadValue = squad.reduce((sum, row) => sum + row.current_price, 0);
    const saleValue = squad.reduce((sum, row) => sum + (row.selling_price ?? row.current_price), 0);
    const purchaseValue = squad.reduce((sum, row) => sum + (row.purchase_price ?? row.current_price), 0);
    return {
      counts,
      squadValue,
      saleValue,
      purchaseValue,
      averageForwardDelta: squad.length ? squad.reduce((sum, row) => sum + row.forward_delta, 0) / squad.length : 0,
      belowPar: squad.filter((row) => row.return_delta != null && row.return_delta < 0).length,
      lowConfidence: squad.filter((row) => confidenceLabel(row.projection_confidence) === "LOW").length,
      tracked: squad.filter((row) => trackedIds.has(row.player_id)).length,
    };
  }, [squad, trackedIds]);

  const visiblePlayers = players;

  const recentTrend = detail?.recent_gameweeks.map((row) => ({ ...row, price: row.value })) ?? [];
  const snapshotTrend = detail?.tracked_snapshots ?? [];

  function changeSort(key: SortKey) {
    setPage(1);
    if (sortKey === key) setSortDirection(sortDirection === "desc" ? "asc" : "desc");
    else {
      setSortKey(key);
      setSortDirection("desc");
    }
  }

  function changeSortOption(option: SortOption) {
    setPage(1);
    setSortOption(option);
    if (option === "CHEAPEST") {
      setSortKey("current_price");
      setSortDirection("asc");
    } else {
      const keys: Record<Exclude<SortOption, "CHEAPEST">, SortKey> = { BEST_VALUE: "forward_delta", PERFORMANCE: "performance_delta" };
      setSortKey(keys[option]);
      setSortDirection("desc");
    }
  }

  function selectPlayer(row: BoardRow) {
    fetch(`${API}/players/${row.player_id}?season=${SEASON}`).then((response) => response.json()).then(setDetail).catch(() => setDetail(null));
  }

  function track(row: BoardRow) {
    fetch(`${API}/tracked-players/${row.player_id}?season=${SEASON}`, { method: "POST" }).then(loadData).catch(() => undefined);
  }

  function untrack(row: BoardRow) {
    fetch(`${API}/tracked-players/${row.player_id}?season=${SEASON}`, { method: "DELETE" }).then(loadData).catch(() => undefined);
  }

  function addSquadPlayer(playerId: number, price: number) {
    fetch(`${API}/squad/${playerId}?${new URLSearchParams({ season: SEASON, purchase_price: price.toString() })}`, { method: "POST" }).then(loadSquad).catch(() => undefined);
  }

  function addSelectedSquadPlayer() {
    const player = players.find((row) => row.player_id === Number(squadPlayerId));
    if (player) addSquadPlayer(player.player_id, Number(purchasePrice || player.current_price));
  }

  function removeSquadPlayer(row: BoardRow) {
    fetch(`${API}/squad/${row.player_id}?season=${SEASON}`, { method: "DELETE" }).then(loadSquad).catch(() => undefined);
  }

  function saveTeamId() {
    if (!teamId) return;
    setTeamMessage("Importing latest public squad...");
    fetch(`${API}/settings/fpl-team?${new URLSearchParams({ season: SEASON, team_id: teamId })}`, { method: "POST" })
      .then((response) => response.json())
      .then((result) => {
        setTeamMessage(`Imported ${result.players} players from public GW${result.gameweek || "-"} picks.`);
        loadData();
      })
      .catch(() => setTeamMessage("Could not import that public FPL team."));
  }

  function viewMarket(row: BoardRow) {
    setPosition(row.position);
    setMaxPrice(row.current_price.toFixed(1));
    setQuickFilter("ALL");
    window.location.hash = "players";
  }

  function saveRoles() {
    if (!detail?.current) return;
    const params = new URLSearchParams({
      penalties: roleForm.penalties ? "1" : "0",
      direct_free_kicks: roleForm.direct_free_kicks ? "1" : "0",
      corners: roleForm.corners ? "1" : "0",
      indirect_free_kicks: roleForm.indirect_free_kicks ? "1" : "0",
      reason: roleForm.reason || "manual role update",
      season: SEASON,
    });
    fetch(`${API}/role-overrides/${detail.current.player_id}?${params}`, { method: "POST" }).then(() => selectPlayer(detail.current)).catch(() => undefined);
  }

  function saveMinutes() {
    if (!detail?.current) return;
    const params = new URLSearchParams({ ...minutesForm, reason: minutesForm.reason || "manual minutes update", season: SEASON });
    fetch(`${API}/minutes-overrides/${detail.current.player_id}?${params}`, { method: "POST" }).then(() => { selectPlayer(detail.current); loadData(); }).catch(() => undefined);
  }

  return (
    <main>
      <header>
        <h1>FPL Analytics</h1>
        <p>Diagnose your squad, discover market value, then investigate the players that matter.</p>
        <nav>
          <a href="#my-squad">Squad</a>
          <a href="#players">Players</a>
          <a href="#data-model">Data / Model</a>
        </nav>
      </header>

      <section className="grid">
        <article id="my-squad" className="wide">
          <h2>My Squad</h2>
          <div className="toolbar">
            <input aria-label="FPL Team ID" type="number" placeholder="FPL Team ID" value={teamId} onChange={(event) => setTeamId(event.target.value)} />
            <button className="action primary" onClick={saveTeamId}>Import Public Squad</button>
            <select aria-label="Squad player" value={squadPlayerId} onChange={(event) => {
              const id = event.target.value;
              const player = players.find((row) => row.player_id === Number(id));
              setSquadPlayerId(id);
              setPurchasePrice(player ? player.current_price.toFixed(1) : "");
            }}>
              <option value="">Add player manually</option>
              {players.filter((row) => !squadIds.has(row.player_id)).map((row) => <option key={row.player_id} value={row.player_id}>{row.player} {row.position} £{row.current_price.toFixed(1)}</option>)}
            </select>
            <input aria-label="Purchase price" type="number" step="0.1" placeholder="Purchase price" value={purchasePrice} onChange={(event) => setPurchasePrice(event.target.value)} />
            <button className="action" onClick={addSelectedSquadPlayer}>Add</button>
          </div>
          <p className="note">{teamMessage || "Public import uses the latest available FPL Gameweek picks, not private transfer drafts."}</p>
          <div className="overview">
            <div className="overview-item"><span>Avg Forward Delta</span><strong className={squadSummary.averageForwardDelta >= 0 ? "positive" : "negative"}>{squadSummary.averageForwardDelta.toFixed(2)}</strong><small>Next-6 vs Par</small></div>
            <div className="overview-item"><span>Below Par</span><strong>{squadSummary.belowPar}</strong><small>historical</small></div>
            <div className="overview-item"><span>Low Confidence</span><strong>{squadSummary.lowConfidence}</strong><small>players</small></div>
            <div className="overview-item"><span>Tracked</span><strong>{squadSummary.tracked}</strong><small>squad players</small></div>
            <div className="overview-item"><span>Squad Value</span><strong>{money(squadSummary.squadValue)}</strong><small>current prices</small></div>
            <div className="overview-item"><span>Sell Value</span><strong>{money(squadSummary.saleValue)}</strong><small>transfer value</small></div>
            <div className="overview-item"><span>Locked Gain</span><strong className={valueTone(squadSummary.saleValue - squadSummary.purchaseValue)}>{signedMetric(squadSummary.saleValue - squadSummary.purchaseValue)}</strong><small>sale less paid</small></div>
          </div>
          <table>
            <thead>
              <tr>
                <th>Player</th><th>Pos</th><th>Price</th>
                <th><HeaderHelp label="Actual pts" tip={tooltipText.actual_points} /></th>
                <th><HeaderHelp label="Par" tip={tooltipText.value_par} /></th>
                <th><HeaderHelp label="Return Δ" tip={tooltipText.return_delta} /></th>
                <th><HeaderHelp label="Underlying xPPG" tip={tooltipText.underlying_xppg} /></th>
                <th><HeaderHelp label="Performance Δ" tip={tooltipText.performance_delta} /></th>
                <th><HeaderHelp label="Forward Δ" tip={tooltipText.forward_delta} /></th>
                <th>Track</th><th></th>
              </tr>
            </thead>
            <tbody>
              {squad.map((row) => (
                <tr key={`squad-${row.player_id}`}>
                  <td><button className="link" onClick={() => selectPlayer(row)}>{row.player}</button></td>
                  <td>{row.position}</td><td>£{row.current_price.toFixed(1)}</td>
                  <td>{metric(row.actual_points, 0)}</td>
                  <td>{metric(row.value_par)}</td>
                  <td className={valueTone(row.return_delta)}>{signedMetric(row.return_delta)}</td>
                  <td>{metric(row.process_xppg_regressed)}</td>
                  <td><DeltaPopover row={row} kind="performance" performanceCache={performanceLineage} forwardCache={forwardLineage} setPerformanceCache={setPerformanceLineage} setForwardCache={setForwardLineage} selectPlayer={selectPlayer} /></td>
                  <td><DeltaPopover row={row} kind="forward" performanceCache={performanceLineage} forwardCache={forwardLineage} setPerformanceCache={setPerformanceLineage} setForwardCache={setForwardLineage} selectPlayer={selectPlayer} /></td>
                  <td>{trackedIds.has(row.player_id) ? <button className="action" onClick={() => untrack(row)}>Untrack</button> : <button className="action" onClick={() => track(row)}>Track</button>}</td>
                  <td><button className="action" onClick={() => viewMarket(row)}>Explore {row.position}</button> <button className="action" onClick={() => removeSquadPlayer(row)}>Remove</button></td>
                </tr>
              ))}
              {squad.length === 0 && <tr><td colSpan={11}>Import your public FPL team or add players manually.</td></tr>}
            </tbody>
          </table>
        </article>

        <article id="players" className="wide">
          <h2>Players</h2>
          <div className="toolbar chips">
            {[
              ["ALL", "All"],
              ["ABOVE_PAR", "Above Par"],
              ["BELOW_PAR", "Below Par"],
              ["EMERGING", "Emerging"],
              ["REGRESSION_RISK", "Regression Risk"],
              ["TRACKED", "Tracked"],
            ].map(([value, label]) => <button key={value} className={quickFilter === value ? "action primary" : "action"} onClick={() => { setQuickFilter(value); setPage(1); }}>{label}</button>)}
          </div>
          <div className="toolbar">
            <input aria-label="Search players" placeholder="Search player or team" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} />
            <select aria-label="Position filter" value={position} onChange={(event) => { setPosition(event.target.value); setPage(1); }}>{positions.map((option) => <option key={option} value={option}>{option}</option>)}</select>
            <input aria-label="Minimum price" type="number" step="0.1" placeholder="Min £" value={minPrice} onChange={(event) => { setMinPrice(event.target.value); setPage(1); }} />
            <input aria-label="Maximum price" type="number" step="0.1" placeholder="Max £" value={maxPrice} onChange={(event) => { setMaxPrice(event.target.value); setPage(1); }} />
            <select aria-label="Confidence filter" value={confidence} onChange={(event) => { setConfidence(event.target.value); setPage(1); }}><option value="ALL">All confidence</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select>
            <select aria-label="Sort players" value={sortOption} onChange={(event) => changeSortOption(event.target.value as SortOption)}>
              <option value="BEST_VALUE">Best Value</option>
              <option value="PERFORMANCE">Best Process</option>
              <option value="CHEAPEST">Cheapest</option>
            </select>
            <label className="check"><input type="checkbox" checked={trackedOnly} onChange={(event) => { setTrackedOnly(event.target.checked); setPage(1); }} /> Tracked only</label>
          </div>
          <div className="pagination"><span>Showing {playersPage.total ? (playersPage.page - 1) * playersPage.page_size + 1 : 0}–{Math.min(playersPage.page * playersPage.page_size, playersPage.total)} of {playersPage.total}</span><button className="action" disabled={playersPage.page <= 1 || playersLoading} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button>{Array.from({ length: Math.min(5, playersPage.total_pages) }, (_, index) => Math.max(1, Math.min(playersPage.total_pages - 4, playersPage.page - 2)) + index).map((value) => <button key={value} className={value === playersPage.page ? "action primary" : "action"} disabled={playersLoading} onClick={() => setPage(value)}>{value}</button>)}<button className="action" disabled={playersPage.page >= playersPage.total_pages || playersLoading} onClick={() => setPage((value) => Math.min(playersPage.total_pages, value + 1))}>Next</button></div>
          <table>
            <thead>
              <tr>
                <th>Player</th><th>Pos</th><th><SortButton label="Price" sortKey="current_price" active={sortKey === "current_price"} direction={sortDirection} onSort={changeSort} /></th>
                <th><SortButton label="Actual pts" sortKey="actual_points" active={sortKey === "actual_points"} direction={sortDirection} onSort={changeSort} title={tooltipText.actual_points} /></th>
                <th><SortButton label="Par" sortKey="value_par" active={sortKey === "value_par"} direction={sortDirection} onSort={changeSort} title={tooltipText.value_par} /></th>
                <th><SortButton label="Return Δ" sortKey="return_delta" active={sortKey === "return_delta"} direction={sortDirection} onSort={changeSort} title={tooltipText.return_delta} /></th>
                <th><SortButton label="Underlying xPPG" sortKey="underlying_xppg" active={sortKey === "underlying_xppg"} direction={sortDirection} onSort={changeSort} title={tooltipText.underlying_xppg} /></th>
                <th><SortButton label="Performance Δ" sortKey="performance_delta" active={sortKey === "performance_delta"} direction={sortDirection} onSort={changeSort} title={tooltipText.performance_delta} /></th>
                <th><SortButton label="Forward Δ" sortKey="forward_delta" active={sortKey === "forward_delta"} direction={sortDirection} onSort={changeSort} title={tooltipText.forward_delta} /></th>
                <th>Track</th>
              </tr>
            </thead>
            <tbody>
              {playersLoading && <tr><td colSpan={10}>Loading players...</td></tr>}
              {!playersLoading && visiblePlayers.map((row) => (
                <tr key={`player-${row.player_id}`}>
                  <td><button className="link" onClick={() => selectPlayer(row)}>{row.player}</button><small>{row.team}</small></td><td>{row.position}</td><td>£{row.current_price.toFixed(1)}</td>
                  <td>{metric(row.actual_points, 0)}</td>
                  <td>{metric(row.value_par)}</td>
                  <td className={valueTone(row.return_delta)}>{signedMetric(row.return_delta)}</td>
                  <td>{metric(row.process_xppg_regressed)}</td>
                  <td><DeltaPopover row={row} kind="performance" performanceCache={performanceLineage} forwardCache={forwardLineage} setPerformanceCache={setPerformanceLineage} setForwardCache={setForwardLineage} selectPlayer={selectPlayer} /></td>
                  <td><DeltaPopover row={row} kind="forward" performanceCache={performanceLineage} forwardCache={forwardLineage} setPerformanceCache={setPerformanceLineage} setForwardCache={setForwardLineage} selectPlayer={selectPlayer} /></td>
                  <td>{trackedIds.has(row.player_id) ? <button className="action" onClick={() => untrack(row)}>Untrack</button> : <button className="action" onClick={() => track(row)}>Track</button>}</td>
                </tr>
              ))}
              {!playersLoading && visiblePlayers.length === 0 && <tr><td colSpan={10}>No players match these filters.</td></tr>}
            </tbody>
          </table>
        </article>

        {detail?.current && (
          <article className="wide">
            <h2>{detail.current.player}</h2>
            <div className="metrics">
              <span>{detail.current.team}</span><span>{detail.current.position}</span><span>£{detail.current.current_price.toFixed(1)}</span>
              <span className={detail.current.return_delta == null ? "" : detail.current.return_delta >= 0 ? "positive" : "negative"}>Return Δ {metric(detail.current.return_delta)}</span>
              <span title={performanceTitle(detail.current)} className={valueTone(detail.current.performance_delta)}>Performance Δ {signedMetric(detail.current.performance_delta)}</span>
              <span title={performanceTitle(detail.current)}>Process {metric(detail.current.process_xppg_regressed)}</span><span>{detail.current.performance_data_state}</span><span>{priorLabel(detail.current)}</span>
              <span className={detail.current.forward_delta >= 0 ? "positive" : "negative"}>Forward Δ {detail.current.forward_delta >= 0 ? "+" : ""}{detail.current.forward_delta.toFixed(2)}</span>
              <span className={detail.current.value_balance == null ? "" : detail.current.value_balance >= 0 ? "positive" : "negative"}>Balance {metric(detail.current.value_balance)}</span>
              <span>Par {detail.current.value_par.toFixed(2)}</span><span>Mean {detail.current.market_mean.toFixed(2)}</span><span>Actual {metric(detail.current.actual_ppg)}</span>
              <span>Underlying {detail.current.underlying_xppg.toFixed(2)}</span><span>Next 3 {detail.current.next_3_xppg.toFixed(2)}</span><span>Next 6 {detail.current.next_6_xppg.toFixed(2)}</span>
              <span>{trendLabel(detail.current.value_trend)}</span><span>Conf {confidenceLabel(detail.current.projection_confidence)}</span><span>Own {detail.current.ownership?.toFixed(1) ?? "-"}%</span>
              <span>Exp Min {detail.current.expected_minutes.toFixed(0)}</span><span>Start {Math.round(detail.current.start_probability * 100)}%</span><span>Minutes {detail.current.minutes_confidence}</span>
              <span>Opp xGA6 {metric(detail.current.expected_opponent_goals_6)}</span>{detail.current.fixture_factor_6 != null && <span>Fixture {detail.current.fixture_factor_6.toFixed(2)}x</span>}{detail.current.captain_adjusted_delta != null && <span className={valueTone(detail.current.captain_adjusted_delta)}>Captain Δ {signedMetric(detail.current.captain_adjusted_delta)}</span>}{detail.current.opportunity_score != null && <span>Opportunity {metric(detail.current.opportunity_score)}</span>}
              {detail.current.raw_xg != null && <span>Raw xG {detail.current.raw_xg.toFixed(2)}</span>}{detail.current.raw_xa != null && <span>Raw xA {detail.current.raw_xa.toFixed(2)}</span>}{detail.current.xg90 != null && <span>xG90 {detail.current.xg90.toFixed(2)}</span>}{detail.current.xa90 != null && <span>xA90 {detail.current.xa90.toFixed(2)}</span>}{detail.current.role_xppg > 0 && <span>Role +{detail.current.role_xppg.toFixed(2)}</span>}{detail.current.clean_sheet_xppg_6 > 0 && <span>CS {detail.current.clean_sheet_xppg_6.toFixed(2)}</span>}{detail.current.defcon_xppg > 0 && <span>DefCon {detail.current.defcon_xppg.toFixed(2)}</span>}{detail.current.bonus_xppg > 0 && <span>Bonus {detail.current.bonus_xppg.toFixed(2)}</span>}{detail.current.save_xppg > 0 && <span>Saves {detail.current.save_xppg.toFixed(2)}</span>}
            </div>
            <h3>Attacking Roles</h3>
            <div className="role-form">
              {(["penalties", "direct_free_kicks", "corners", "indirect_free_kicks"] as const).map((key) => <label key={key}><input type="checkbox" checked={roleForm[key]} onChange={(event) => setRoleForm({ ...roleForm, [key]: event.target.checked })} />{key.replace(/_/g, " ")}</label>)}
              <input aria-label="Role reason" placeholder="Reason" value={roleForm.reason} onChange={(event) => setRoleForm({ ...roleForm, reason: event.target.value })} />
              <button onClick={saveRoles}>Save Roles</button>
              {trackedIds.has(detail.current.player_id) ? <button className="action" onClick={() => untrack(detail.current)}>Untrack</button> : <button className="action" onClick={() => track(detail.current)}>Track</button>}
            </div>
            <h3>Minutes Override</h3>
            <div className="role-form">
              <input aria-label="Start probability" type="number" min="0" max="1" step="0.05" placeholder="Start prob 0-1" value={minutesForm.start_probability} onChange={(event) => setMinutesForm({ ...minutesForm, start_probability: event.target.value })} />
              <input aria-label="Minutes if starting" type="number" min="0" max="90" step="1" placeholder="Start min" value={minutesForm.expected_minutes_if_starting} onChange={(event) => setMinutesForm({ ...minutesForm, expected_minutes_if_starting: event.target.value })} />
              <input aria-label="Substitute probability" type="number" min="0" max="1" step="0.05" placeholder="Sub prob 0-1" value={minutesForm.substitute_probability} onChange={(event) => setMinutesForm({ ...minutesForm, substitute_probability: event.target.value })} />
              <input aria-label="Minutes if substitute" type="number" min="0" max="90" step="1" placeholder="Sub min" value={minutesForm.expected_minutes_if_sub} onChange={(event) => setMinutesForm({ ...minutesForm, expected_minutes_if_sub: event.target.value })} />
              <input aria-label="Minutes reason" placeholder="Reason" value={minutesForm.reason} onChange={(event) => setMinutesForm({ ...minutesForm, reason: event.target.value })} />
              <button onClick={saveMinutes}>Save Minutes</button>
            </div>
            <div className="chart-grid">
              {recentTrend.length > 0 && <div><h3>Recent Points And Minutes</h3><ResponsiveContainer width="100%" height={220}><LineChart data={recentTrend}><XAxis dataKey="gameweek" /><YAxis /><Tooltip /><Legend /><Line type="monotone" dataKey="total_points" name="Points" stroke="#2563eb" /><Line type="monotone" dataKey="minutes" name="Minutes" stroke="#16a34a" /></LineChart></ResponsiveContainer></div>}
              {snapshotTrend.length > 0 && <div><h3>Tracked Forward Delta And Price</h3><ResponsiveContainer width="100%" height={220}><LineChart data={snapshotTrend}><XAxis dataKey="gameweek" /><YAxis /><Tooltip /><Legend /><Line type="monotone" dataKey="buy_delta" name="Forward Delta" stroke="#b91c1c" /><Line type="monotone" dataKey="price" name="Price" stroke="#7c3aed" /></LineChart></ResponsiveContainer></div>}
            </div>
            <h3>Projection Breakdown</h3>
            <table><tbody>{Object.entries(detail.projection_breakdown).map(([key, value]) => <tr key={key}><td>{key.replace(/_/g, " ")}</td><td>{value.toFixed(2)}</td></tr>)}</tbody></table>
            {detail.current.fixture_projection && detail.current.fixture_projection.length > 0 && (
              <>
                <h3>Next Fixtures</h3>
                <table>
                  <thead><tr><th>GW</th><th>Fixture</th><th>Attack</th><th>xGA</th><th>Goal</th><th>Assist</th><th>CS</th><th>DefCon</th><th>Bonus</th><th>Saves</th><th>Total</th></tr></thead>
                  <tbody>
                    {detail.current.fixture_projection.flatMap((gw) => gw.fixtures.length ? gw.fixtures.map((fixture, index) => (
                      <tr key={`${gw.gameweek}-${fixture.fixture_id}`}>
                        <td>{index === 0 ? gw.gameweek : ""}</td><td>{fixture.is_home ? "H" : "A"} vs {fixtureOpponent(fixture)}</td><td>{Number(fixture.attack_factor).toFixed(2)}</td><td>{Number(fixture.expected_goals_against).toFixed(2)}</td><td>{Number(fixture.goal_ev).toFixed(2)}</td><td>{Number(fixture.assist_ev).toFixed(2)}</td><td>{Number(fixture.clean_sheet_ev).toFixed(2)}</td><td>{Number(fixture.defcon_ev).toFixed(2)}</td><td>{Number(fixture.bonus_ev).toFixed(2)}</td><td>{Number(fixture.save_ev).toFixed(2)}</td><td>{Number(fixture.total_fixture_xpts).toFixed(2)}</td>
                      </tr>
                    )) : [<tr key={`${gw.gameweek}-blank`}><td>{gw.gameweek}</td><td>Blank</td><td colSpan={8}></td><td>0.00</td></tr>])}
                  </tbody>
                </table>
              </>
            )}
            <h3>Recent Gameweeks</h3>
            <table><thead><tr><th>GW</th><th>Pts</th><th>Min</th><th>Price</th></tr></thead><tbody>{detail.recent_gameweeks.map((row) => <tr key={row.gameweek}><td>{row.gameweek}</td><td>{row.total_points}</td><td>{row.minutes}</td><td>{row.value ? `£${row.value.toFixed(1)}` : "-"}</td></tr>)}{detail.recent_gameweeks.length === 0 && <tr><td colSpan={4}>No gameweek history yet</td></tr>}</tbody></table>
          </article>
        )}

        {points.map((point, index) => point.position).filter((position, index, list) => list.indexOf(position) === index).map((position) => {
          const rows = points.filter((point) => point.position === position);
          return <article key={position}><h2>{position}</h2><ResponsiveContainer width="100%" height={180}><LineChart data={rows}><XAxis dataKey="price" /><YAxis domain={["dataMin", "dataMax"]} /><Tooltip /><Line type="monotone" dataKey="market_mean" stroke="#2563eb" dot={false} /><Line type="monotone" dataKey="value_par" stroke="#16a34a" dot={false} /></LineChart></ResponsiveContainer></article>;
        })}
      </section>
    </main>
  );
}

const root = document.getElementById("root");
if (root) createRoot(root).render(<App />);
