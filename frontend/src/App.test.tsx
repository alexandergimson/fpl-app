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
    role_xppg: 0,
    clean_sheet_xppg_6: 0,
    defcon_xppg: 0,
    bonus_xppg: 0,
    save_xppg: 0,
    expected_opponent_goals_6: 1.35,
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

beforeEach(() => {
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
    if (url.includes("/squad")) return json([]) as Promise<Response>;
    if (url.includes("/alerts")) return json([]) as Promise<Response>;
    if (url.includes("/price-movements")) return json([]) as Promise<Response>;
    if (url.includes("/data-status")) return json({ season: "2026-27", health_summary: {}, latest_ingestion_runs: [], latest_health_events: [], sources: [] }) as Promise<Response>;
    if (url.includes("/price-par")) return json([]) as Promise<Response>;
    if (url.includes("/players/1")) return json({ current: players[0], projection_breakdown: { fixture_xpts: 3 }, recent_gameweeks: [], minutes_history: [], role_history: [], tracked_snapshots: [] }) as Promise<Response>;
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
