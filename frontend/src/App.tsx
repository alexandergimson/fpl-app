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
  season_points?: number | null;
  games?: number | null;
  matches_played?: number;
  market_mean: number;
  expected_ppg?: number | null;
  value_par: number;
  value_balance: number | null;
  actual_ppg: number | null;
  par_ppg: number;
  performance_ppg: number | null;
  next_6_ppg: number;
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
  fixture_projection?: { gameweek: number; total_xpts: number; fixtures: Record<string, number | string | boolean | null>[] }[];
  next_5_fixtures?: Record<string, number | string | boolean | null>[];
  team_context?: TeamContext;
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
  purchase_price_source?: string;
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
  shots: number | null;
  shots_in_box: number | null;
  high_quality_chances: number | null;
  high_quality_chances_created: number | null;
  key_passes: number | null;
  penalties: number;
  direct_free_kicks: number;
  corners: number;
  indirect_free_kicks: number;
  role_override_reason?: string | null;
  minutes_override_reason?: string | null;
};

type TeamContext = {
  team_xg: number | null;
  team_xga: number | null;
  team_xg_last_5: number | null;
  team_xga_last_5: number | null;
  team_shots_conceded: number | null;
  team_high_quality_chances_conceded: number | null;
};

type PlayerDetail = {
  player: { id: number; name: string; team: string | null; position: string; current_price: number };
  current: BoardRow;
  projection_breakdown: Record<string, number>;
  recent_gameweeks: { gameweek: number; total_points: number; minutes: number; value: number }[];
  gameweeks: { gameweek: number; opponent: string | null; home_away: string | null; points: number | null; project_score: number | null; performance: number | null; xg: number | null; xa: number | null; minutes: number | null; price: number | null; model_run_id: number | null; forecast_data_cutoff: string | null }[];
  gameweek_history: { gameweek: number; points: number; minutes: number; price: number | null; price_change: number | null; xg: number | null; xa: number | null; game_underlying_xpts: number | null; frozen_par: number | null; performance_vs_par: number | null }[];
  prediction_history: { gameweek: number; model_run_id: number; created_at: string; data_cutoff: string | null; model_version: string; current_price: number | null; actual_ppg: number | null; value_par: number | null; current_par: number | null; return_delta: number | null; performance_delta: number | null; neutral_xppg: number | null; next_3_xppg: number | null; next_6_xppg: number | null; forward_delta: number | null; buy_delta_6: number | null; expected_minutes: number | null; projection_confidence: number | null; fixture_factor_6: number | null; xg90: number | null; xa90: number | null }[];
  minutes_history: { start_probability: number; expected_minutes_if_starting: number; substitute_probability: number; expected_minutes_if_sub: number; reason: string; created_at: string }[];
  role_history: { penalties: number; direct_free_kicks: number; corners: number; indirect_free_kicks: number; reason: string; created_at: string }[];
};

type PlayersPage = { players: BoardRow[]; page: number; page_size: number; total: number; total_pages: number };
type RefreshSummary = { status: string; gameweek: number; players: number; fixtures: number; observations: number; team_underlying: number; materialized: number; snapshots: number; alerts: number };
type ManagerContext = { bank: number | null; free_transfers: number | null; chips_remaining: string[] | null; deadline: string | null; context_type: string | null };
type Settings = { fpl_team_id?: number | null; manager?: ManagerContext };
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

type AnalysisComparison = { key: string; label: string; raw: number; per_90: number | null; positional_average: number | null; percentile: number | null; price_average: number | null; price_band: number; cohort_size: number; rate_basis: "per90" | "per_shot" | "per_game" | "save_percentage" };
type AnalysisGame = { gameweek: number; opponent: string | null; minutes: number; points: number; starts: number; goals: number; assists: number; bonus: number; bps: number; saves: number; clean_sheets: number; goals_conceded: number; xg: number | null; xa: number | null; xgi: number | null; shots: number | null; shots_in_box: number | null; shots_on_target: number | null; key_passes: number | null; penalty_shots: number | null; penalty_xg: number | null; direct_free_kick_shots: number | null; team_xg_conceded: number | null; performance_points: number | null; actual_minus_performance: number | null; cumulative_actual_ppg: number; cumulative_performance_ppg: number | null; benchmark_eligible: boolean; benchmark_minutes: number; headline_metric_keys: string[]; comparisons: AnalysisComparison[] };
type AnalysisAggregate = { window: "last5" | "season"; available_windows: ("last5" | "season")[]; appearances: number; minutes: number; from_gameweek: number | null; to_gameweek: number | null; benchmark_eligible: boolean; benchmark_minutes: number; cohort_size: number; price_cohort_size: number; price_band: number; comparisons: AnalysisComparison[] };
type PlayerAnalysis = { player: { player_id: number; web_name: string; team: string; position: string; current_price: number }; headline: { actual_ppg: number | null; par_ppg: number | null; performance_ppg: number | null; next_6_ppg: number | null; return_delta: number | null; performance_delta: number | null; forward_delta: number | null; process_gap: number | null; performance_data_state: string }; aggregate: AnalysisAggregate; diagnosis: string; games: AnalysisGame[] };

type SortKey =
  | "player"
  | "position"
  | "current_price"
  | "actual_points"
  | "season_points"
  | "matches_played"
  | "actual_ppg"
  | "par_ppg"
  | "performance_ppg"
  | "next_6_ppg"
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

type SortOption = "BEST_VALUE" | "PERFORMANCE" | "CHEAPEST" | "CUSTOM";

const API = "http://127.0.0.1:8000";
const SEASON = "2026-27";
const tooltipText = {
  season_points: "Total FPL points scored this season.",
  matches_played: "Matches in which the player recorded at least one minute.",
  actual_ppg: "Actual FPL points per elapsed Gameweek.",
  par_ppg: "Expected PPG for a player at this price and position.",
  performance_ppg: "Expected PPG based on the player's aggregated underlying performance.",
  next_6_ppg: "Projected average PPG across the next six Gameweeks.",
  return_delta: "Actual PPG minus Par PPG.",
  underlying_xppg: "Estimated FPL points per game based on underlying performance rather than actual points scored.",
  performance_delta: "Performance PPG minus Par PPG.",
  forward_delta: "Next 6 PPG minus Par PPG.",};


function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" }) : "not loaded";
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


function chipsLabel(chips: string[] | null | undefined) {
  if (chips == null) return "—";
  return chips.length;
}

function chipsNote(chips: string[] | null | undefined) {
  if (chips == null) return "unavailable";
  return chips.join(", ") || "none remaining";
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
      <div className="popover-grid"><span>Performance PPG</span><strong>{metric(lineage.underlying_xppg)}</strong><span>Par PPG</span><strong>{metric(lineage.value_par)}</strong><span>Performance Δ</span><strong>{signedMetric(lineage.performance_delta)}</strong><span>State</span><strong>{lineage.state}</strong></div>
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
      <div className="popover-grid"><span>Next 6 PPG</span><strong>{metric(lineage.next_6_xppg)}</strong><span>Par PPG</span><strong>{metric(lineage.value_par)}</strong><span>Forward Δ</span><strong>{signedMetric(lineage.forward_delta)}</strong></div>
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

function sortValue(row: BoardRow, key: SortKey) {
  return row[key as keyof BoardRow];
}

function compareRows(a: BoardRow, b: BoardRow, key: SortKey, direction: "asc" | "desc") {
  const left = sortValue(a, key);
  const right = sortValue(b, key);
  if (left == null && right == null) return a.player.localeCompare(b.player);
  if (left == null) return 1;
  if (right == null) return -1;
  const result = typeof left === "string" || typeof right === "string" ? String(left).localeCompare(String(right)) : Number(left) - Number(right);
  return direction === "asc" ? result : -result;
}

export function App() {
  const [players, setPlayers] = useState<BoardRow[]>([]);
  const [points, setPoints] = useState<ParPoint[]>([]);
  const [playersPage, setPlayersPage] = useState<PlayersPage>({ players: [], page: 1, page_size: 15, total: 0, total_pages: 1 });
  const [playersLoading, setPlayersLoading] = useState(false);
  const [squad, setSquad] = useState<BoardRow[]>([]);
  const [detail, setDetail] = useState<PlayerDetail | null>(null);
  const [analysis, setAnalysis] = useState<PlayerAnalysis | null>(null);
  const [expandedGameweek, setExpandedGameweek] = useState<number | null>(null);
  const [teamId, setTeamId] = useState("");
  const [manager, setManager] = useState<ManagerContext | null>(null);
  const [teamMessage, setTeamMessage] = useState("");
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("ALL");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [confidence, setConfidence] = useState("ALL");
  const [quickFilter, setQuickFilter] = useState("ALL");
  const [squadPlayerId, setSquadPlayerId] = useState("");
  const [purchasePrice, setPurchasePrice] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("forward_delta");
  const [sortDirection, setSortDirection] = useState<"desc" | "asc">("desc");
  const [sortOption, setSortOption] = useState<SortOption>("BEST_VALUE");
  const [page, setPage] = useState(1);
  const [dataVersion, setDataVersion] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState("");
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

  fetch(`${API}/settings?season=${SEASON}`)
    .then((response) => response.json())
    .then((settings: Settings) => {
      setTeamId(settings.fpl_team_id?.toString() ?? "");
      setManager(settings.manager ?? null);
    })
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
  }, [page, sortKey, sortDirection, position, minPrice, maxPrice, search, quickFilter, confidence, dataVersion]);

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

  const squadIds = useMemo(() => new Set(squad.map((row) => row.player_id)), [squad]);
  const positions = ["ALL", "GK", "DEF", "MID", "FWD"];
  const squadSummary = useMemo(() => {
    const counts = { STRONG: 0, HEALTHY: 0, WATCH: 0, REVIEW: 0 };
    squad.forEach((row) => counts[row.squad_health as keyof typeof counts]++);
    const squadValue = squad.reduce((sum, row) => sum + row.current_price, 0);
    const saleValue = squad.reduce((sum, row) => sum + (row.selling_price ?? row.current_price), 0);
    const purchaseValue = squad.reduce((sum, row) => sum + (row.purchase_price ?? row.current_price), 0);
    const hasGenuinePurchasePrices = squad.length > 0 && squad.every((row) => row.purchase_price_source !== "public_current_price_fallback");
    return {
      counts,
      squadValue,
      saleValue,
      purchaseValue,
      hasGenuinePurchasePrices,
      averageForwardDelta: squad.length ? squad.reduce((sum, row) => sum + row.forward_delta, 0) / squad.length : 0,
      belowPar: squad.filter((row) => row.return_delta != null && row.return_delta < 0).length,
      lowConfidence: squad.filter((row) => confidenceLabel(row.projection_confidence) === "LOW").length,
    };
  }, [squad]);

  const visiblePlayers = players;
  const visibleSquad = useMemo(() => [...squad].sort((a, b) => compareRows(a, b, sortKey, sortDirection)), [squad, sortKey, sortDirection]);

  function changeSort(key: SortKey) {
    setPage(1);
    setSortOption("CUSTOM");
    if (sortKey === key) setSortDirection(sortDirection === "desc" ? "asc" : "desc");
    else {
      setSortKey(key);
      setSortDirection("desc");
    }
  }

  function changeSortOption(option: SortOption) {
    setPage(1);
    setSortOption(option);
    if (option === "CUSTOM") return;
    if (option === "CHEAPEST") {
      setSortKey("current_price");
      setSortDirection("asc");
    } else {
      const keys: Record<Exclude<SortOption, "CHEAPEST" | "CUSTOM">, SortKey> = { BEST_VALUE: "forward_delta", PERFORMANCE: "performance_delta" };
      setSortKey(keys[option]);
      setSortDirection("desc");
    }
  }

  function selectPlayer(row: BoardRow) {
    setExpandedGameweek(null);
    Promise.all([
      fetch(`${API}/players/${row.player_id}?season=${SEASON}`).then((response) => response.json()),
      fetch(`${API}/players/${row.player_id}/analysis?season=${SEASON}`).then((response) => response.json()),
    ]).then(([playerDetail, playerAnalysis]) => { setDetail(playerDetail); setAnalysis(playerAnalysis); }).catch(() => { setDetail(null); setAnalysis(null); });
  }

  function selectAnalysisWindow(window: "last5" | "season") {
    if (!analysis) return;
    fetch(`${API}/players/${analysis.player.player_id}/analysis?season=${SEASON}&window=${window}`)
      .then((response) => response.json())
      .then(setAnalysis)
      .catch(() => undefined);
  }

  function refreshData() {
    setRefreshing(true);
    setRefreshMessage("");
    fetch(`${API}/refresh?season=${SEASON}`, { method: "POST" })
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.detail || "Refresh failed");
        return body as RefreshSummary;
      })
      .then((summary) => {
        setRefreshMessage(`Updated GW${summary.gameweek} · ${summary.players} players · ${summary.materialized} metrics`);
        loadData();
        setDataVersion((value) => value + 1);
        if (detail?.current) selectPlayer(detail.current);
      })
      .catch((error) => setRefreshMessage(error.message))
      .finally(() => setRefreshing(false));
  }

  function addSquadPlayer(playerId: number, price: number) {
    fetch(`${API}/squad/${playerId}?${new URLSearchParams({ season: SEASON, purchase_price: price.toString() })}`, { method: "POST" }).then(loadSquad).catch(() => undefined);
  }

  function addSelectedSquadPlayer() {
    const player = players.find((row) => row.player_id === Number(squadPlayerId));
    if (player) addSquadPlayer(player.player_id, Number(purchasePrice || player.current_price));
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




  return (
    <main>
      <header>
        <div>
        <h1>FPL Analytics</h1>
        <p>Diagnose your squad, discover market value, then investigate the players that matter.</p>
        <nav>
          <button className="action primary" type="button" onClick={refreshData} disabled={refreshing}>{refreshing ? "Refreshing…" : "Refresh Data"}</button>
        </nav>
        {refreshMessage && <p className="note">{refreshMessage}</p>}
        </div>
      </header>
      <section className="grid">
        <article id="my-squad" className="wide">
          <h2>My Squad</h2>
          <div className="toolbar">
            <input aria-label="FPL Team ID" type="number" placeholder="FPL Team ID" value={teamId} onChange={(event) => setTeamId(event.target.value)} />
            <button className="action primary" onClick={saveTeamId}>Import Public Squad</button>
          </div>


          <table>
<thead>
  <tr>
    <th><SortButton label="Player" sortKey="player" active={sortKey === "player"} direction={sortDirection} onSort={changeSort} title="Player name and current club." /></th>
    <th><SortButton label="Pos" sortKey="position" active={sortKey === "position"} direction={sortDirection} onSort={changeSort} title="FPL position: goalkeeper, defender, midfielder or forward." /></th>
    <th><SortButton label="Price" sortKey="current_price" active={sortKey === "current_price"} direction={sortDirection} onSort={changeSort} title="Current FPL price." /></th>
    <th><SortButton label="Total Pts" sortKey="season_points" active={sortKey === "season_points"} direction={sortDirection} onSort={changeSort} title={tooltipText.season_points} /></th>
    <th><SortButton label="Played" sortKey="matches_played" active={sortKey === "matches_played"} direction={sortDirection} onSort={changeSort} title={tooltipText.matches_played} /></th>
    <th><SortButton label="Actual PPG" sortKey="actual_ppg" active={sortKey === "actual_ppg"} direction={sortDirection} onSort={changeSort} title={tooltipText.actual_ppg} /></th>
    <th><SortButton label="Par PPG" sortKey="par_ppg" active={sortKey === "par_ppg"} direction={sortDirection} onSort={changeSort} title={tooltipText.par_ppg} /></th>
    <th><SortButton label="Performance PPG" sortKey="performance_ppg" active={sortKey === "performance_ppg"} direction={sortDirection} onSort={changeSort} title={tooltipText.performance_ppg} /></th>
    <th><SortButton label="Next 6 PPG" sortKey="next_6_ppg" active={sortKey === "next_6_ppg"} direction={sortDirection} onSort={changeSort} title={tooltipText.next_6_ppg} /></th>
    <th><SortButton label="Return Δ" sortKey="return_delta" active={sortKey === "return_delta"} direction={sortDirection} onSort={changeSort} title={tooltipText.return_delta} /></th>
    <th><SortButton label="Performance Δ" sortKey="performance_delta" active={sortKey === "performance_delta"} direction={sortDirection} onSort={changeSort} title={tooltipText.performance_delta} /></th>
    <th><SortButton label="Forward Δ" sortKey="forward_delta" active={sortKey === "forward_delta"} direction={sortDirection} onSort={changeSort} title={tooltipText.forward_delta} /></th>
    <th></th>
  </tr>
</thead>
            <tbody>
              {visibleSquad.map((row) => (
                <tr key={`squad-${row.player_id}`}>
                  <td><button className="link" onClick={() => selectPlayer(row)}>{row.player}</button></td>
                  <td>{row.position}</td><td>£{row.current_price.toFixed(1)}</td>
                  <td>{metric(row.season_points, 0)}</td>
                  <td>{row.matches_played ?? 0}</td>
                  <td><strong>{metric(row.actual_ppg)}</strong></td>
                  <td>{metric(row.par_ppg)}</td>
                  <td>{metric(row.performance_ppg)}</td>
                  <td>{metric(row.next_6_ppg)}</td>
                  <td className={valueTone(row.return_delta)}>{signedMetric(row.return_delta)}</td>
                  <td><DeltaPopover row={row} kind="performance" performanceCache={performanceLineage} forwardCache={forwardLineage} setPerformanceCache={setPerformanceLineage} setForwardCache={setForwardLineage} selectPlayer={selectPlayer} /></td>
                  <td><DeltaPopover row={row} kind="forward" performanceCache={performanceLineage} forwardCache={forwardLineage} setPerformanceCache={setPerformanceLineage} setForwardCache={setForwardLineage} selectPlayer={selectPlayer} /></td>
                  <td><button className="action" onClick={() => selectPlayer(row)}>Analyse</button></td>
                </tr>
              ))}
              {squad.length === 0 && <tr><td colSpan={13}>Import your public FPL team or add players manually.</td></tr>}
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
            ].map(([value, label]) => <button key={value} className={quickFilter === value ? "action primary" : "action"} onClick={() => { setQuickFilter(value); setPage(1); }}>{label}</button>)}
          </div>
          <div className="toolbar">
            <input aria-label="Search players" placeholder="Search player or team" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} />
            <select aria-label="Position filter" value={position} onChange={(event) => { setPosition(event.target.value); setPage(1); }}>{positions.map((option) => <option key={option} value={option}>{option}</option>)}</select>
            <input aria-label="Minimum price" type="number" step="0.1" placeholder="Min £" value={minPrice} onChange={(event) => { setMinPrice(event.target.value); setPage(1); }} />
            <input aria-label="Maximum price" type="number" step="0.1" placeholder="Max £" value={maxPrice} onChange={(event) => { setMaxPrice(event.target.value); setPage(1); }} />
            <select aria-label="Confidence filter" value={confidence} onChange={(event) => { setConfidence(event.target.value); setPage(1); }}><option value="ALL">All confidence</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select>
            <select aria-label="Sort players" value={sortOption} onChange={(event) => changeSortOption(event.target.value as SortOption)}>
              <option value="CUSTOM">Custom sort</option>
              <option value="BEST_VALUE">Best Value</option>
              <option value="PERFORMANCE">Best Process</option>
              <option value="CHEAPEST">Cheapest</option>
            </select>
          </div>
          <div className="pagination"><span>Showing {playersPage.total ? (playersPage.page - 1) * playersPage.page_size + 1 : 0}–{Math.min(playersPage.page * playersPage.page_size, playersPage.total)} of {playersPage.total}</span><button className="action" disabled={playersPage.page <= 1 || playersLoading} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button>{Array.from({ length: Math.min(5, playersPage.total_pages) }, (_, index) => Math.max(1, Math.min(playersPage.total_pages - 4, playersPage.page - 2)) + index).map((value) => <button key={value} className={value === playersPage.page ? "action primary" : "action"} disabled={playersLoading} onClick={() => setPage(value)}>{value}</button>)}<button className="action" disabled={playersPage.page >= playersPage.total_pages || playersLoading} onClick={() => setPage((value) => Math.min(playersPage.total_pages, value + 1))}>Next</button></div>
          <table>
<thead>
  <tr>
    <th><SortButton label="Player" sortKey="player" active={sortKey === "player"} direction={sortDirection} onSort={changeSort} title="Player name and current club." /></th>
    <th><SortButton label="Pos" sortKey="position" active={sortKey === "position"} direction={sortDirection} onSort={changeSort} title="FPL position: goalkeeper, defender, midfielder or forward." /></th>
    <th><SortButton label="Price" sortKey="current_price" active={sortKey === "current_price"} direction={sortDirection} onSort={changeSort} title="Current FPL price." /></th>
    <th><SortButton label="Total Pts" sortKey="season_points" active={sortKey === "season_points"} direction={sortDirection} onSort={changeSort} title={tooltipText.season_points} /></th>
    <th><SortButton label="Played" sortKey="matches_played" active={sortKey === "matches_played"} direction={sortDirection} onSort={changeSort} title={tooltipText.matches_played} /></th>
    <th><SortButton label="Actual PPG" sortKey="actual_ppg" active={sortKey === "actual_ppg"} direction={sortDirection} onSort={changeSort} title={tooltipText.actual_ppg} /></th>
    <th><SortButton label="Par PPG" sortKey="par_ppg" active={sortKey === "par_ppg"} direction={sortDirection} onSort={changeSort} title={tooltipText.par_ppg} /></th>
    <th><SortButton label="Performance PPG" sortKey="performance_ppg" active={sortKey === "performance_ppg"} direction={sortDirection} onSort={changeSort} title={tooltipText.performance_ppg} /></th>
    <th><SortButton label="Next 6 PPG" sortKey="next_6_ppg" active={sortKey === "next_6_ppg"} direction={sortDirection} onSort={changeSort} title={tooltipText.next_6_ppg} /></th>
    <th><SortButton label="Return Δ" sortKey="return_delta" active={sortKey === "return_delta"} direction={sortDirection} onSort={changeSort} title={tooltipText.return_delta} /></th>
    <th><SortButton label="Performance Δ" sortKey="performance_delta" active={sortKey === "performance_delta"} direction={sortDirection} onSort={changeSort} title={tooltipText.performance_delta} /></th>
    <th><SortButton label="Forward Δ" sortKey="forward_delta" active={sortKey === "forward_delta"} direction={sortDirection} onSort={changeSort} title={tooltipText.forward_delta} /></th>
    <th></th>
  </tr>
</thead>
            <tbody>
              {playersLoading && <tr><td colSpan={13}>Loading players...</td></tr>}
              {!playersLoading && visiblePlayers.map((row) => (
                <tr key={`player-${row.player_id}`}>
                  <td><button className="link" onClick={() => selectPlayer(row)}>{row.player}</button><small>{row.team}</small></td><td>{row.position}</td><td>£{row.current_price.toFixed(1)}</td>
                  <td>{metric(row.season_points, 0)}</td>
                  <td>{row.matches_played ?? 0}</td>
                  <td><strong>{metric(row.actual_ppg)}</strong></td>
                  <td>{metric(row.par_ppg)}</td>
                  <td>{metric(row.performance_ppg)}</td>
                  <td>{metric(row.next_6_ppg)}</td>
                  <td className={valueTone(row.return_delta)}>{signedMetric(row.return_delta)}</td>
                  <td><DeltaPopover row={row} kind="performance" performanceCache={performanceLineage} forwardCache={forwardLineage} setPerformanceCache={setPerformanceLineage} setForwardCache={setForwardLineage} selectPlayer={selectPlayer} /></td>
                  <td><DeltaPopover row={row} kind="forward" performanceCache={performanceLineage} forwardCache={forwardLineage} setPerformanceCache={setPerformanceLineage} setForwardCache={setForwardLineage} selectPlayer={selectPlayer} /></td>
                  <td><button className="action" onClick={() => selectPlayer(row)}>Analyse</button></td>
                </tr>
              ))}
              {!playersLoading && visiblePlayers.length === 0 && <tr><td colSpan={13}>No players match these filters.</td></tr>}
            </tbody>
          </table>
        </article>

        {detail?.current && analysis?.headline && (
          <article className="wide">
            <h2>{detail.player.name} · {detail.player.team ?? "—"} · {detail.player.position} · £{detail.player.current_price.toFixed(1)}m</h2>
            <div className="analysis-summary">
              <div><span>Actual PPG</span><strong>{metric(analysis.headline.actual_ppg)}</strong></div>
              <div><span>Par PPG</span><strong>{metric(analysis.headline.par_ppg)}</strong></div>
              <div><span>Performance PPG</span><strong>{metric(analysis.headline.performance_ppg)}</strong></div>
              <div><span>Next 6 PPG</span><strong>{metric(analysis.headline.next_6_ppg)}</strong></div>
            </div>
            <div className="analysis-window" aria-label="Analysis window">
              {analysis.aggregate.available_windows.includes("last5") && <button className={analysis.aggregate.window === "last5" ? "active" : ""} onClick={() => selectAnalysisWindow("last5")}>Last 5 matches</button>}
              <button className={analysis.aggregate.window === "season" ? "active" : ""} onClick={() => selectAnalysisWindow("season")}>Season</button>
              <small>{analysis.aggregate.appearances} appearances · {analysis.aggregate.minutes} minutes</small>
            </div>
            {!analysis.aggregate.benchmark_eligible && analysis.aggregate.minutes > 0 && <p className="note">Raw evidence only: {analysis.aggregate.benchmark_minutes} cumulative minutes are required for positional percentiles.</p>}
            <table className="analysis-comparison">
              <thead><tr><th>Metric</th><th>Player</th><th>Position avg</th><th>Percentile</th><th>Price avg</th></tr></thead>
              <tbody>
                {analysis.aggregate.comparisons.map((item) => <tr key={item.key}><td>{item.label}{item.rate_basis === "per90" ? " / 90" : item.rate_basis === "per_shot" ? " / shot" : ""}</td><td><strong>{metric(item.raw)}</strong></td><td>{metric(item.positional_average)}</td><td>{item.percentile == null ? "—" : `${item.percentile}th`}</td><td>{metric(item.price_average)}</td></tr>)}
                {analysis.aggregate.comparisons.length === 0 && <tr><td colSpan={5}>No aggregate evidence available</td></tr>}
              </tbody>
            </table>
            <p className="note">Position cohort: {analysis.aggregate.cohort_size} eligible {analysis.player.position}s · Price cohort: {analysis.aggregate.price_cohort_size} within ±£{analysis.aggregate.price_band.toFixed(1)}m</p>
            <p className="diagnosis"><strong>{analysis.diagnosis}</strong><br />Return Δ {signedMetric(analysis.headline.return_delta)} · Performance Δ {signedMetric(analysis.headline.performance_delta)} · Forward Δ {signedMetric(analysis.headline.forward_delta)} · Process gap {signedMetric(analysis.headline.process_gap)}</p>
            <details className="match-breakdown">
              <summary>Match breakdown ({analysis.games.length})</summary>
              <table>
                <thead><tr><th>GW</th><th>Opponent</th><th>Min</th><th>Pts</th><th>Perf Pts</th>{(analysis.games[0]?.headline_metric_keys ?? []).map((key) => <th key={key}>{analysis.games.flatMap((game) => game.comparisons).find((item) => item.key === key)?.label ?? key}</th>)}<th></th></tr></thead>
                <tbody>
                  {analysis.games.map((game) => (
                    <React.Fragment key={game.gameweek}>
                      <tr><td>{game.gameweek}</td><td>{game.opponent ?? "—"}</td><td>{game.minutes}</td><td>{game.points}</td><td>{metric(game.performance_points)}</td>{game.headline_metric_keys.map((key) => <td key={key}>{metric(game.comparisons.find((item) => item.key === key)?.raw)}</td>)}<td><button className="action" onClick={() => setExpandedGameweek(expandedGameweek === game.gameweek ? null : game.gameweek)}>{expandedGameweek === game.gameweek ? "Close" : "Evidence"}</button></td></tr>
                      {expandedGameweek === game.gameweek && <tr className="evidence-row"><td colSpan={6 + game.headline_metric_keys.length}><div className="evidence-panel">
                        <h3>GW{game.gameweek} vs {game.opponent ?? "—"} — {game.minutes} mins</h3>
                        <p>Actual points: <strong>{game.points}</strong> · Performance points: <strong>{metric(game.performance_points)}</strong> · Difference: <strong className={valueTone(game.actual_minus_performance)}>{signedMetric(game.actual_minus_performance)}</strong></p>
                        {!game.benchmark_eligible && <p className="note">Raw evidence only: {game.benchmark_minutes} cumulative minutes are required for percentiles at this point.</p>}
                        <table><thead><tr><th>Metric</th><th>Player</th><th>Rate</th><th>Position avg</th><th>Percentile</th><th>Price avg</th></tr></thead><tbody>{game.comparisons.map((item) => <tr key={item.key}><td>{item.label}</td><td>{metric(item.raw)}</td><td>{metric(item.rate_basis === "per90" ? item.per_90 : item.raw)}</td><td>{metric(item.positional_average)}</td><td>{item.percentile == null ? "—" : `${item.percentile}th`}</td><td>{metric(item.price_average)}</td></tr>)}</tbody></table>
                        <div className="evidence-outcomes"><span>Goals <strong>{game.goals}</strong></span><span>Assists <strong>{game.assists}</strong></span><span>Bonus <strong>{game.bonus}</strong></span><span>BPS <strong>{game.bps}</strong></span><span>xGI <strong>{metric(game.xgi)}</strong></span><span>Actual PPG <strong>{metric(game.cumulative_actual_ppg)}</strong></span><span>Performance PPG <strong>{metric(game.cumulative_performance_ppg)}</strong></span><span>Team xGC <strong>{metric(game.team_xg_conceded)}</strong></span></div>
                      </div></td></tr>}
                    </React.Fragment>
                  ))}
                  {analysis.games.length === 0 && <tr><td colSpan={8}>No game evidence yet</td></tr>}
                </tbody>
              </table>
            </details>
          </article>
        )}

        {points.map((point) => point.position).filter((position, index, list) => list.indexOf(position) === index).map((position) => {
          const rows = points.filter((point) => point.position === position);
          return <article key={position}><h2>{position}</h2><ResponsiveContainer width="100%" height={180}><LineChart data={rows}><XAxis dataKey="price" /><YAxis domain={["dataMin", "dataMax"]} /><Tooltip /><Line type="monotone" dataKey="market_mean" stroke="#2563eb" dot={false} /><Line type="monotone" dataKey="value_par" stroke="#16a34a" dot={false} /></LineChart></ResponsiveContainer></article>;
        })}
      </section>
    </main>
  );
}

const root = document.getElementById("root");
if (root) createRoot(root).render(<App />);
