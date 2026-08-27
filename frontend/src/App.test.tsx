import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { App } from "./App";

const players = [
  row({ player_id: 1, player: "Zero", position: "MID", current_price: 6, performance_delta: 0, forward_delta: 0.5, tracking_status: "TRACKED" }),
  row({ player_id: 2, player: "Null", position: "FWD", current_price: 5, performance_delta: null, forward_delta: -0.2 }),
  row({ player_id: 3, player: "Plus", position: "DEF", current_price: 7, performance_delta: 0.3, forward_delta: 1.2 }),
  ...Array.from({ length: 17 }, (_, index) => row({ player_id: index + 4, player: `Page${index + 4}`, position: "MID", current_price: 8 + index, performance_delta: -0.1, forward_delta: -1 })),
];

function row(overrides: Partial<Record<string, unknown>>) {
  return {
    player_id: 0,
    player: "Player",
    team: "TST",
    position: "MID",
    current_price: 5,
    market_mean: 3,
    value_par: 3,
    value_balance: null,
    actual_ppg: null,
    historical_delta: null,
    return_delta: null,
    neutral_xppg: 3,
    underlying_xppg: 3,
    process_xppg_regressed: 3,
    performance_delta: null,
    performance_data_state: "sufficient",
    performance_confidence: "LOW",
    performance_sample_gameweeks: 1,
    performance_sample_minutes: 90,
    next_3_xppg: 3,
    next_6_xppg: 3,
    buy_delta_6: 0,
    forward_delta: 0,
    expected_minutes: 90,
    start_probability: 1,
    projection_confidence: 0.8,
    minutes_confidence: "HIGH",
    value_trend: 0,
    price_trend: 0,
    ownership: 1,
    is_emerging: false,
    is_regression_risk: false,
  status: "WATCH",
    purchase_price_source: "manual",
    role_xppg: 0,
    clean_sheet_xppg_6: 0,
    defcon_xppg: 0,
    bonus_xppg: 0,
    save_xppg: 0,
    expected_opponent_goals_6: 1.35,
    fixture_factor_6: 1,
    captain_adjusted_delta: 0,
    opportunity_score: 0,
    shots: 0,
    shots_in_box: 0,
    high_quality_chances: 0,
    high_quality_chances_created: 0,
    key_passes: 0,
    penalties: 0,
    direct_free_kicks: 0,
    corners: 0,
    indirect_free_kicks: 0,
    prior_source: "historical_position_price",
    prior_confidence: "LOW",
    prior_minutes: 900,
    ...overrides,
  };
}

function json(data: unknown) {
  return Promise.resolve({ json: () => Promise.resolve(data) });
}

let squadResponse: unknown[] = [];
let settingsResponse: unknown = {};
let detailResponse: unknown = {};

beforeEach(() => {
  squadResponse = [];
  settingsResponse = { fpl_team_id: null, manager: { bank: null, free_transfers: null, chips_remaining: null, deadline: null, context_type: "public" } };
  detailResponse = { current: players[0], projection_breakdown: { fixture_xpts: 3 }, recent_gameweeks: [], minutes_history: [], role_history: [], tracked_snapshots: [] };
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.includes("/all-players")) {
      const parsed = new URL(url);
      let rows = [...players];
      const position = parsed.searchParams.get("position");
      if (position && position !== "ALL") rows = rows.filter((item) => item.position === position);
      const minPrice = Number(parsed.searchParams.get("min_price") || "");
      const maxPrice = Number(parsed.searchParams.get("max_price") || "");
      if (minPrice) rows = rows.filter((item) => item.current_price >= minPrice);
      if (maxPrice) rows = rows.filter((item) => item.current_price <= maxPrice);
      if (parsed.searchParams.get("tracked") === "true") rows = rows.filter((item) => item.player_id === 1);
      const sort = parsed.searchParams.get("sort");
      const direction = parsed.searchParams.get("direction") === "asc" ? 1 : -1;
      if (sort) rows.sort((a, b) => (Number((a as Record<string, unknown>)[sort] ?? 0) - Number((b as Record<string, unknown>)[sort] ?? 0)) * direction);
      const page = Number(parsed.searchParams.get("page") || 1);
      const pageSize = Number(parsed.searchParams.get("page_size") || 15);
      return json({ players: rows.slice((page - 1) * pageSize, page * pageSize), page, page_size: pageSize, total: rows.length, total_pages: Math.ceil(rows.length / pageSize) || 1 }) as Promise<Response>;
    }
    if (url.includes("/players/1/performance-lineage")) return json({ player_id: 1, performance_delta: 0, underlying_xppg: 3, value_par: 3, state: "sufficient", confidence: "LOW", sample_gameweeks: 1, sample_minutes: 90, prior: { source: "historical_position_price", confidence: "LOW" }, components: { appearance: 2, goal: 0, assist: 0, clean_sheet: 0, defcon: 0, bonus: 0, saves: 0, deductions: 0 }, available_observations: ["official FPL player process"], missing_required_observations: [], forward_available: true, note: "Based on underlying performance, not actual FPL points." }) as Promise<Response>;
    if (url.includes("/players/1/forward-lineage")) return json({ player_id: 1, forward_delta: 0.5, next_6_xppg: 3.5, value_par: 3, gameweeks: [{ gameweek: 2, projected_points: 3.5, fixtures: [{ opponent: "ARS", home_away: "H", expected_minutes: 90, total_xpts: 3.5 }] }] }) as Promise<Response>;
    if (url.includes("/tracked-players")) return json([players[0]]) as Promise<Response>;
    if (url.includes("/squad")) return json(squadResponse) as Promise<Response>;
    if (url.includes("/alerts")) return json([]) as Promise<Response>;
    if (url.includes("/price-movements")) return json([]) as Promise<Response>;
    if (url.includes("/data-status")) return json({ season: "2026-27", health_summary: {}, latest_ingestion_runs: [], latest_health_events: [], sources: [] }) as Promise<Response>;
    if (url.includes("/price-par")) return json([]) as Promise<Response>;
    if (url.includes("/settings")) return json(settingsResponse) as Promise<Response>;
    if (url.includes("/players/1")) return json(detailResponse) as Promise<Response>;
    return json({}) as Promise<Response>;
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function playersArticle() {
  const headings = screen.getAllByRole("heading", { name: "Players" });
  return headings[headings.length - 1].closest("article")!;
}

test("renders null and zero Performance Delta distinctly", async () => {
  render(<App />);
  expect(await screen.findByText("Zero")).toBeInTheDocument();
  const playersTable = playersArticle();
  expect(within(playersTable).getByRole("row", { name: /Zero/ })).toHaveTextContent("+0.00");
  expect(within(playersTable).getByRole("row", { name: /Null/ })).toHaveTextContent("—");
});

test("styles positive and negative deltas", async () => {
  render(<App />);
  expect(await screen.findByText("Plus")).toBeInTheDocument();
  const playersTable = playersArticle();
  expect(within(within(playersTable).getByRole("row", { name: /Plus/ })).getByText("+0.30")).toHaveClass("positive");
  expect(within(within(playersTable).getByRole("row", { name: /Null/ })).getByText("-0.20")).toHaveClass("negative");
});

test("sorts, filters, tracks, and opens detail", async () => {
  render(<App />);
  expect((await screen.findAllByText("Zero")).length).toBeGreaterThan(0);
  const playersTable = playersArticle();
  fireEvent.change(screen.getByLabelText("Sort players"), { target: { value: "CHEAPEST" } });
  await waitFor(() => expect(within(within(playersTable).getAllByRole("row")[1]).getByText("Null")).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("Position filter"), { target: { value: "DEF" } });
  await waitFor(() => expect(within(playersTable).getByText("Plus")).toBeInTheDocument());
  expect(within(playersTable).queryByText("Zero")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Position filter"), { target: { value: "ALL" } });
  fireEvent.change(screen.getByLabelText("Minimum price"), { target: { value: "6" } });
  fireEvent.change(screen.getByLabelText("Maximum price"), { target: { value: "6" } });
  await waitFor(() => expect(within(playersTable).getByText("Zero")).toBeInTheDocument());
  expect(within(playersTable).queryByText("Plus")).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Tracked only"));
  await waitFor(() => expect(within(playersTable).getByText("Zero")).toBeInTheDocument());
  fireEvent.click(within(playersTable).getByRole("button", { name: "Zero" }));
  expect(await screen.findByText("Projection Breakdown")).toBeInTheDocument();
});

test("renders selected canonical player team and fixture context in detail", async () => {
  detailResponse = {
    current: row({
      player_id: 1,
      player: "Zero",
      shots: 3,
      shots_in_box: 2,
      high_quality_chances: 1,
      high_quality_chances_created: 1,
      key_passes: 4,
      team_context: { team_xg: 4, team_xga: 2, team_xg_last_5: 3, team_xga_last_5: 1.5, team_shots_conceded: 12, team_high_quality_chances_conceded: 3 },
      next_5_fixtures: [{ gameweek: 2, opponent_team_id: 9, opponent: "ARS", home_away: "H", fdr: 2, opponent_attacking_strength: 1100, opponent_defensive_strength: 900 }],
      fixture_projection: [{ gameweek: 2, total_xpts: 3.5, fixtures: [{ fixture_id: 1, gameweek: 2, opponent_team_id: 9, opponent: "ARS", is_home: true, attack_factor: 1.1, expected_goals_against: 0.9, goal_ev: 0.5, assist_ev: 0.2, clean_sheet_ev: 0.1, defcon_ev: 0, bonus_ev: 0.1, save_ev: 0, total_fixture_xpts: 3.5 }] }],
    }),
    projection_breakdown: { fixture_xpts: 3 },
    recent_gameweeks: [],
    minutes_history: [],
    role_history: [],
    tracked_snapshots: [],
  };
  render(<App />);
  await screen.findByText("Zero");
  fireEvent.click(within(playersArticle()).getByRole("button", { name: "Zero" }));
  expect(await screen.findByText("Shots 3")).toBeInTheDocument();
  expect(screen.getByText("HQ Created 1")).toBeInTheDocument();
  expect(screen.getByText("Team Form")).toBeInTheDocument();
  expect(screen.getByText("xG L5")).toBeInTheDocument();
  expect(screen.getByText("Opp Atk")).toBeInTheDocument();
  expect(screen.getByText("1100")).toBeInTheDocument();
});

test("renders manager context without inventing private fields", async () => {
  settingsResponse = { fpl_team_id: 123, manager: { bank: null, free_transfers: null, chips_remaining: ["freehit", "wildcard"], deadline: "2026-08-29T10:00:00Z", context_type: "public" } };
  render(<App />);
  expect(await screen.findByText("Bank")).toBeInTheDocument();
  expect(screen.getAllByText("unavailable").length).toBeGreaterThan(0);
  expect(screen.getByText("freehit, wildcard")).toBeInTheDocument();
  expect(screen.getByText(/29\/08\/2026/)).toBeInTheDocument();
});

test("renders unavailable canonical metrics as dashes", async () => {
  detailResponse = {
    current: row({
      player_id: 1,
      player: "Zero",
      shots: null,
      shots_in_box: null,
      high_quality_chances: null,
      high_quality_chances_created: null,
      key_passes: null,
      team_context: { team_xg: null, team_xga: null, team_xg_last_5: null, team_xga_last_5: null, team_shots_conceded: null, team_high_quality_chances_conceded: null },
    }),
    projection_breakdown: { fixture_xpts: 3 },
    recent_gameweeks: [],
    minutes_history: [],
    role_history: [],
    tracked_snapshots: [],
  };
  render(<App />);
  await screen.findByText("Zero");
  fireEvent.click(within(playersArticle()).getByRole("button", { name: "Zero" }));
  expect(await screen.findByText("Shots —")).toBeInTheDocument();
  expect(screen.getByText("HQ Chances —")).toBeInTheDocument();
  expect(screen.getByText("HQ Created —")).toBeInTheDocument();
  expect(screen.getAllByText("—").length).toBeGreaterThan(1);
  expect(screen.getAllByText("unavailable").length).toBeGreaterThan(0);
});

test("hides locked gain when squad purchase prices are public fallbacks", async () => {
  squadResponse = [row({ player_id: 1, player: "Zero", purchase_price: 6, selling_price: 6.2, purchase_price_source: "public_current_price_fallback" })];
  render(<App />);
  expect(await screen.findByText("Squad Value")).toBeInTheDocument();
  expect(screen.queryByText("Locked Gain")).not.toBeInTheDocument();
});

test("players page renders 15 rows and paginates", async () => {
  render(<App />);
  expect(await screen.findByText("Showing 1–15 of 20")).toBeInTheDocument();
  expect(within(playersArticle()).getAllByRole("row")).toHaveLength(16);
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(await screen.findByText("Showing 16–20 of 20")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Previous" }));
  expect(await screen.findByText("Showing 1–15 of 20")).toBeInTheDocument();
});

test("filter resets players pagination to page 1", async () => {
  render(<App />);
  await screen.findByText("Showing 1–15 of 20");
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(await screen.findByText("Showing 16–20 of 20")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Position filter"), { target: { value: "DEF" } });
  expect(await screen.findByText("Showing 1–1 of 1")).toBeInTheDocument();
});

test("lineage loads only when a delta is inspected", async () => {
  const fetchMock = vi.mocked(globalThis.fetch);
  render(<App />);
  await screen.findByText("Zero");
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes("performance-lineage"))).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Performance Delta for Zero" }));
  expect(await screen.findByText("Based on underlying performance, not actual FPL points.")).toBeInTheDocument();
  expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("performance-lineage")).length).toBe(1);
});
