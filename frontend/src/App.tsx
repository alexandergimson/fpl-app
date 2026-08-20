import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import "./style.css";

type ParPoint = {
  position: string;
  price: number;
  market_mean: number;
  value_par: number;
  sample_size: number;
  confidence: string;
};

type BoardRow = {
  player_id: number;
  player: string;
  team: string;
  position: string;
  current_price: number;
  value_par: number;
  actual_ppg: number;
  neutral_xppg: number;
  next_6_xppg: number;
  buy_delta_6: number;
  captain_adjusted_delta: number;
  opportunity_score: number;
  expected_minutes: number;
  xg90?: number | null;
  xa90?: number | null;
  role_xppg: number;
  clean_sheet_xppg_6: number;
  defcon_xppg: number;
  bonus_xppg: number;
  save_xppg: number;
  expected_opponent_goals_6: number;
  penalties: number;
  direct_free_kicks: number;
  corners: number;
  indirect_free_kicks: number;
  role_override_reason?: string | null;
  minutes_confidence: string;
  minutes_override_reason?: string | null;
  fixture_factor_6: number;
  status: string;
  breakout_gap?: number;
  trap_gap?: number;
  selling_price?: number;
  hold_delta?: number;
  best_replacement?: string;
  transfer_gain?: number;
  squad_verdict?: string;
  delta_momentum?: number;
  tracking_status?: string;
};

type PlayerDetail = {
  current: BoardRow;
  projection_breakdown: Record<string, number>;
  recent_gameweeks: { gameweek: number; total_points: number; minutes: number; value: number }[];
  role_history: {
    penalties: number;
    direct_free_kicks: number;
    corners: number;
    indirect_free_kicks: number;
    reason: string;
    created_at: string;
  }[];
  tracked_snapshots: { gameweek: number; buy_delta: number; price: number }[];
};

type Alert = {
  id: number;
  kind: string;
  message: string;
  created_at: string;
};

type PriceMovement = {
  player_id: number;
  player: string;
  team: string;
  position: string;
  first_price: number;
  latest_price: number;
  price_change: number;
  gameweek?: number | null;
};

type SortKey = "buy_delta_6" | "captain_adjusted_delta" | "opportunity_score" | "next_6_xppg" | "current_price" | "expected_minutes";

function App() {
  const [points, setPoints] = useState<ParPoint[]>([]);
  const [board, setBoard] = useState<BoardRow[]>([]);
  const [breakouts, setBreakouts] = useState<BoardRow[]>([]);
  const [traps, setTraps] = useState<BoardRow[]>([]);
  const [tracked, setTracked] = useState<BoardRow[]>([]);
  const [squad, setSquad] = useState<BoardRow[]>([]);
  const [detail, setDetail] = useState<PlayerDetail | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [priceMovements, setPriceMovements] = useState<PriceMovement[]>([]);
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("ALL");
  const [bank, setBank] = useState(0);
  const [squadPlayerId, setSquadPlayerId] = useState("");
  const [purchasePrice, setPurchasePrice] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("buy_delta_6");
  const [sortDirection, setSortDirection] = useState<"desc" | "asc">("desc");
  const [roleForm, setRoleForm] = useState({
    penalties: false,
    direct_free_kicks: false,
    corners: false,
    indirect_free_kicks: false,
    reason: "",
  });

  function loadSquad(bankValue = bank) {
    fetch(`http://127.0.0.1:8000/squad?season=2026-27&bank=${bankValue}`)
      .then((response) => response.json())
      .then(setSquad)
      .catch(() => setSquad([]));
  }

  function loadData() {
    fetch("http://127.0.0.1:8000/price-par")
      .then((response) => response.json())
      .then(setPoints)
      .catch(() => setPoints([]));
    fetch("http://127.0.0.1:8000/buy-board?season=2026-27&limit=25")
      .then((response) => response.json())
      .then(setBoard)
      .catch(() => setBoard([]));
    fetch("http://127.0.0.1:8000/breakout-board?season=2026-27&limit=10")
      .then((response) => response.json())
      .then(setBreakouts)
      .catch(() => setBreakouts([]));
    fetch("http://127.0.0.1:8000/trap-board?season=2026-27&limit=10")
      .then((response) => response.json())
      .then(setTraps)
      .catch(() => setTraps([]));
    fetch("http://127.0.0.1:8000/tracked-players?season=2026-27")
      .then((response) => response.json())
      .then(setTracked)
      .catch(() => setTracked([]));
    loadSquad();
    fetch("http://127.0.0.1:8000/alerts?season=2026-27")
      .then((response) => response.json())
      .then(setAlerts)
      .catch(() => setAlerts([]));
    fetch("http://127.0.0.1:8000/price-movements?season=2026-27&limit=10")
      .then((response) => response.json())
      .then(setPriceMovements)
      .catch(() => setPriceMovements([]));
  }

  useEffect(() => {
    loadData();
  }, []);

  const positions = [...new Set(points.map((point) => point.position))];
  const trackedIds = useMemo(() => new Set(tracked.map((row) => row.player_id)), [tracked]);
  const squadIds = useMemo(() => new Set(squad.map((row) => row.player_id)), [squad]);
  const boardPositions = ["ALL", ...[...new Set(board.map((row) => row.position))].sort()];
  const visibleBoard = useMemo(() => {
    const query = search.trim().toLowerCase();
    return board
      .filter((row) => position === "ALL" || row.position === position)
      .filter((row) => !query || row.player.toLowerCase().includes(query) || row.team.toLowerCase().includes(query))
      .sort((a, b) => {
        const direction = sortDirection === "desc" ? -1 : 1;
        return (a[sortKey] - b[sortKey]) * direction;
      });
  }, [board, position, search, sortDirection, sortKey]);
  const recentTrend = useMemo(
    () => detail?.recent_gameweeks.map((row) => ({ ...row, price: row.value })) ?? [],
    [detail],
  );
  const snapshotTrend = useMemo(() => detail?.tracked_snapshots ?? [], [detail]);
  const weakestSquad = useMemo(
    () => [...squad].sort((a, b) => (b.transfer_gain ?? 0) - (a.transfer_gain ?? 0))[0],
    [squad],
  );
  const overview = [
    { label: "Top Buy", value: board[0]?.player ?? "-", detail: board[0] ? `${board[0].buy_delta_6.toFixed(2)} delta` : "" },
    { label: "Breakout", value: breakouts[0]?.player ?? "-", detail: breakouts[0] ? `${(breakouts[0].breakout_gap ?? 0).toFixed(2)} gap` : "" },
    { label: "Trap", value: traps[0]?.player ?? "-", detail: traps[0] ? `${(traps[0].trap_gap ?? 0).toFixed(2)} gap` : "" },
    { label: "Weakest Squad", value: weakestSquad?.player ?? "-", detail: weakestSquad ? `${(weakestSquad.transfer_gain ?? 0).toFixed(2)} gain` : "" },
    { label: "Alerts", value: alerts.length.toString(), detail: "open" },
    { label: "Price Moves", value: priceMovements.length.toString(), detail: "tracked" },
  ];

  function selectPlayer(row: BoardRow) {
    fetch(`http://127.0.0.1:8000/players/${row.player_id}?season=2026-27`)
      .then((response) => response.json())
      .then(setDetail)
      .catch(() => setDetail(null));
  }

  useEffect(() => {
    if (!detail?.current) return;
    setRoleForm({
      penalties: detail.current.penalties > 0,
      direct_free_kicks: detail.current.direct_free_kicks > 0,
      corners: detail.current.corners > 0,
      indirect_free_kicks: detail.current.indirect_free_kicks > 0,
      reason: detail.current.role_override_reason ?? "",
    });
  }, [detail]);

  function changeSort(key: SortKey) {
    if (sortKey === key) {
      setSortDirection(sortDirection === "desc" ? "asc" : "desc");
    } else {
      setSortKey(key);
      setSortDirection("desc");
    }
  }

  function saveRoles() {
    if (!detail?.current) return;
    const params = new URLSearchParams({
      penalties: roleForm.penalties ? "1" : "0",
      direct_free_kicks: roleForm.direct_free_kicks ? "1" : "0",
      corners: roleForm.corners ? "1" : "0",
      indirect_free_kicks: roleForm.indirect_free_kicks ? "1" : "0",
      reason: roleForm.reason || "manual role update",
      season: "2026-27",
    });
    fetch(`http://127.0.0.1:8000/role-overrides/${detail.current.player_id}?${params}`, { method: "POST" })
      .then(() => selectPlayer(detail.current))
      .catch(() => undefined);
  }

  function track(row: BoardRow) {
    fetch(`http://127.0.0.1:8000/tracked-players/${row.player_id}?season=2026-27`, { method: "POST" })
      .then(loadData)
      .catch(() => undefined);
  }

  function untrack(row: BoardRow) {
    fetch(`http://127.0.0.1:8000/tracked-players/${row.player_id}?season=2026-27`, { method: "DELETE" })
      .then(loadData)
      .catch(() => undefined);
  }

  function addSquadPlayer(playerId: number, price: number) {
    const params = new URLSearchParams({
      season: "2026-27",
      purchase_price: price.toString(),
    });
    fetch(`http://127.0.0.1:8000/squad/${playerId}?${params}`, { method: "POST" })
      .then(() => loadSquad())
      .catch(() => undefined);
  }

  function addSelectedSquadPlayer() {
    const player = board.find((row) => row.player_id === Number(squadPlayerId));
    if (!player) return;
    addSquadPlayer(player.player_id, Number(purchasePrice || player.current_price));
  }

  function removeSquadPlayer(row: BoardRow) {
    fetch(`http://127.0.0.1:8000/squad/${row.player_id}?season=2026-27`, { method: "DELETE" })
      .then(() => loadSquad())
      .catch(() => undefined);
  }

  return (
    <main>
      <header>
        <h1>FPL Analytics</h1>
        <p>Price Par curves by position and current price.</p>
      </header>
      <section className="grid">
        <article className="wide">
          <h2>Overview</h2>
          <div className="overview">
            {overview.map((item) => (
              <div className="overview-item" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <small>{item.detail}</small>
              </div>
            ))}
          </div>
        </article>
        <article className="wide">
          <h2>Alerts</h2>
          <table>
            <thead>
              <tr><th>Type</th><th>Message</th><th>Created</th></tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.id}>
                  <td>{alert.kind}</td>
                  <td>{alert.message}</td>
                  <td>{alert.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <article className="wide">
          <h2>Price Movements</h2>
          <table>
            <thead>
              <tr><th>Player</th><th>Pos</th><th>Start</th><th>Now</th><th>Move</th><th>GW</th></tr>
            </thead>
            <tbody>
              {priceMovements.map((row) => (
                <tr key={`price-${row.player_id}`}>
                  <td>{row.player}</td>
                  <td>{row.position}</td>
                  <td>£{row.first_price.toFixed(1)}</td>
                  <td>£{row.latest_price.toFixed(1)}</td>
                  <td className={row.price_change >= 0 ? "positive" : "negative"}>{row.price_change.toFixed(1)}</td>
                  <td>{row.gameweek ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <article className="wide">
          <h2>Buy Board</h2>
          <div className="toolbar">
            <input
              aria-label="Search players"
              placeholder="Search player or team"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <select aria-label="Position filter" value={position} onChange={(event) => setPosition(event.target.value)}>
              {boardPositions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </div>
          <table>
            <thead>
              <tr>
                <th>Player</th>
                <th></th>
                <th></th>
                <th>Pos</th>
                <th><button className="sort" onClick={() => changeSort("current_price")}>Price</button></th>
                <th>Par</th>
                <th><button className="sort" onClick={() => changeSort("next_6_xppg")}>Next 6</button></th>
                <th><button className="sort" onClick={() => changeSort("buy_delta_6")}>Delta</button></th>
                <th><button className="sort" onClick={() => changeSort("captain_adjusted_delta")}>Cap</button></th>
                <th><button className="sort" onClick={() => changeSort("opportunity_score")}>Opp</button></th>
                <th>Fix</th>
                <th><button className="sort" onClick={() => changeSort("expected_minutes")}>Min</button></th>
                <th>Conf</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {visibleBoard.map((row) => (
                <tr key={`${row.player}-${row.position}`}>
                  <td><button className="link" onClick={() => selectPlayer(row)}>{row.player}</button></td>
                  <td>
                    {trackedIds.has(row.player_id) ? (
                      <button className="action" onClick={() => untrack(row)}>Untrack</button>
                    ) : (
                      <button className="action" onClick={() => track(row)}>Track</button>
                    )}
                  </td>
                  <td>
                    {squadIds.has(row.player_id) ? (
                      <button className="action" onClick={() => removeSquadPlayer(row)}>Remove</button>
                    ) : (
                      <button className="action" onClick={() => addSquadPlayer(row.player_id, row.current_price)}>Squad</button>
                    )}
                  </td>
                  <td>{row.position}</td>
                  <td>£{row.current_price.toFixed(1)}</td>
                  <td>{row.value_par.toFixed(2)}</td>
                  <td>{row.next_6_xppg.toFixed(2)}</td>
                  <td className={row.buy_delta_6 >= 0 ? "positive" : "negative"}>{row.buy_delta_6.toFixed(2)}</td>
                  <td className={row.captain_adjusted_delta >= 0 ? "positive" : "negative"}>{row.captain_adjusted_delta.toFixed(2)}</td>
                  <td className={row.opportunity_score >= 0 ? "positive" : "negative"}>{row.opportunity_score.toFixed(2)}</td>
                  <td>{row.fixture_factor_6.toFixed(2)}</td>
                  <td title={row.minutes_override_reason ?? ""}>{row.expected_minutes.toFixed(0)}{row.minutes_override_reason ? "*" : ""}</td>
                  <td>{row.minutes_confidence}</td>
                  <td>{row.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        {detail?.current && (
          <article className="wide">
            <h2>{detail.current.player}</h2>
            <div className="metrics">
              <span>£{detail.current.current_price.toFixed(1)}</span>
              <span>Par {detail.current.value_par.toFixed(2)}</span>
              <span>Next 6 {detail.current.next_6_xppg.toFixed(2)}</span>
              {detail.current.xg90 != null && <span>xG90 {detail.current.xg90.toFixed(2)}</span>}
              {detail.current.xa90 != null && <span>xA90 {detail.current.xa90.toFixed(2)}</span>}
              {detail.current.role_xppg > 0 && <span>Role +{detail.current.role_xppg.toFixed(2)}</span>}
              {detail.current.clean_sheet_xppg_6 > 0 && <span>CS {detail.current.clean_sheet_xppg_6.toFixed(2)}</span>}
              {detail.current.defcon_xppg > 0 && <span>DefCon {detail.current.defcon_xppg.toFixed(2)}</span>}
              {detail.current.bonus_xppg > 0 && <span>Bonus {detail.current.bonus_xppg.toFixed(2)}</span>}
              {detail.current.save_xppg > 0 && <span>Saves {detail.current.save_xppg.toFixed(2)}</span>}
              {detail.current.expected_opponent_goals_6 > 0 && <span>Opp xG {detail.current.expected_opponent_goals_6.toFixed(2)}</span>}
              <span className={detail.current.buy_delta_6 >= 0 ? "positive" : "negative"}>Delta {detail.current.buy_delta_6.toFixed(2)}</span>
              <span className={detail.current.captain_adjusted_delta >= 0 ? "positive" : "negative"}>Cap Delta {detail.current.captain_adjusted_delta.toFixed(2)}</span>
              <span>{detail.current.status}</span>
            </div>
            <h3>Attacking Roles</h3>
            <div className="role-form">
              {(["penalties", "direct_free_kicks", "corners", "indirect_free_kicks"] as const).map((key) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={roleForm[key]}
                    onChange={(event) => setRoleForm({ ...roleForm, [key]: event.target.checked })}
                  />
                  {key.replace(/_/g, " ")}
                </label>
              ))}
              <input
                aria-label="Role reason"
                placeholder="Reason"
                value={roleForm.reason}
                onChange={(event) => setRoleForm({ ...roleForm, reason: event.target.value })}
              />
              <button onClick={saveRoles}>Save Roles</button>
            </div>
            {detail.role_history.length > 0 && (
              <p className="note">Latest: {detail.role_history[0].reason}</p>
            )}
            <div className="chart-grid">
              {recentTrend.length > 0 && (
                <div>
                  <h3>Recent Points And Minutes</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={recentTrend}>
                      <XAxis dataKey="gameweek" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Line type="monotone" dataKey="total_points" name="Points" stroke="#2563eb" />
                      <Line type="monotone" dataKey="minutes" name="Minutes" stroke="#16a34a" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              {snapshotTrend.length > 0 && (
                <div>
                  <h3>Tracked Delta And Price</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={snapshotTrend}>
                      <XAxis dataKey="gameweek" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Line type="monotone" dataKey="buy_delta" name="Buy Delta" stroke="#b91c1c" />
                      <Line type="monotone" dataKey="price" name="Price" stroke="#7c3aed" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
            <h3>Projection Breakdown</h3>
            <table>
              <tbody>
                {Object.entries(detail.projection_breakdown).map(([key, value]) => (
                  <tr key={key}>
                    <td>{key.replace(/_/g, " ")}</td>
                    <td>{value.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h3>Recent Gameweeks</h3>
            <table>
              <thead>
                <tr><th>GW</th><th>Pts</th><th>Min</th><th>Price</th></tr>
              </thead>
              <tbody>
                {detail.recent_gameweeks.map((row) => (
                  <tr key={`gw-${row.gameweek}`}>
                    <td>{row.gameweek}</td>
                    <td>{row.total_points}</td>
                    <td>{row.minutes}</td>
                    <td>{row.value ? `£${row.value.toFixed(1)}` : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </article>
        )}
        <article>
          <h2>Breakouts</h2>
          <MiniBoard rows={breakouts} gapKey="breakout_gap" />
        </article>
        <article>
          <h2>Traps</h2>
          <MiniBoard rows={traps} gapKey="trap_gap" />
        </article>
        <article className="wide">
          <h2>Tracked Players</h2>
          <table>
            <thead>
              <tr><th>Player</th><th></th><th>Pos</th><th>Price</th><th>Par</th><th>Next 6</th><th>Delta</th><th>Mom</th><th>Trend</th><th>Status</th></tr>
            </thead>
            <tbody>
              {tracked.map((row) => (
                <tr key={`tracked-${row.player}-${row.position}`}>
                  <td>{row.player}</td>
                  <td><button className="action" onClick={() => untrack(row)}>Untrack</button></td>
                  <td>{row.position}</td>
                  <td>£{row.current_price.toFixed(1)}</td>
                  <td>{row.value_par.toFixed(2)}</td>
                  <td>{row.next_6_xppg.toFixed(2)}</td>
                  <td className={row.buy_delta_6 >= 0 ? "positive" : "negative"}>{row.buy_delta_6.toFixed(2)}</td>
                  <td className={(row.delta_momentum ?? 0) >= 0 ? "positive" : "negative"}>{(row.delta_momentum ?? 0).toFixed(2)}</td>
                  <td>{row.tracking_status ?? "WATCH"}</td>
                  <td>{row.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <article className="wide">
          <h2>My Squad</h2>
          <div className="toolbar">
            <select
              aria-label="Squad player"
              value={squadPlayerId}
              onChange={(event) => {
                const id = event.target.value;
                const player = board.find((row) => row.player_id === Number(id));
                setSquadPlayerId(id);
                setPurchasePrice(player ? player.current_price.toFixed(1) : "");
              }}
            >
              <option value="">Add player</option>
              {board
                .filter((row) => !squadIds.has(row.player_id))
                .map((row) => (
                  <option key={`squad-option-${row.player_id}`} value={row.player_id}>
                    {row.player} {row.position} £{row.current_price.toFixed(1)}
                  </option>
                ))}
            </select>
            <input
              aria-label="Purchase price"
              type="number"
              min="3.5"
              step="0.1"
              placeholder="Purchase price"
              value={purchasePrice}
              onChange={(event) => setPurchasePrice(event.target.value)}
            />
            <button className="action" onClick={addSelectedSquadPlayer}>Add</button>
            <input
              aria-label="Bank"
              type="number"
              min="0"
              step="0.1"
              value={bank}
              onChange={(event) => {
                const value = Number(event.target.value);
                setBank(value);
                loadSquad(value);
              }}
            />
          </div>
          <table>
            <thead>
              <tr><th>Player</th><th></th><th>Pos</th><th>Sell</th><th>Next 6</th><th>Hold</th><th>Replacement</th><th>Gain</th><th>Verdict</th></tr>
            </thead>
            <tbody>
              {squad.map((row) => (
                <tr key={`squad-${row.player}-${row.position}`}>
                  <td>{row.player}</td>
                  <td><button className="action" onClick={() => removeSquadPlayer(row)}>Remove</button></td>
                  <td>{row.position}</td>
                  <td>£{(row.selling_price ?? row.current_price).toFixed(1)}</td>
                  <td>{row.next_6_xppg.toFixed(2)}</td>
                  <td className={(row.hold_delta ?? 0) >= 0 ? "positive" : "negative"}>{(row.hold_delta ?? 0).toFixed(2)}</td>
                  <td>{row.best_replacement ?? "-"}</td>
                  <td className={(row.transfer_gain ?? 0) >= 0 ? "positive" : "negative"}>{(row.transfer_gain ?? 0).toFixed(2)}</td>
                  <td>{row.squad_verdict}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        {positions.map((position) => {
          const rows = points.filter((point) => point.position === position);
          return (
            <article key={position}>
              <h2>{position}</h2>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={rows}>
                  <XAxis dataKey="price" />
                  <YAxis domain={["dataMin", "dataMax"]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="market_mean" stroke="#2563eb" dot={false} />
                  <Line type="monotone" dataKey="value_par" stroke="#16a34a" dot={false} />
                </LineChart>
              </ResponsiveContainer>
              <table>
                <thead>
                  <tr><th>Price</th><th>Mean</th><th>Par</th><th>n</th><th>Conf</th></tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={`${row.position}-${row.price}`}>
                      <td>£{row.price.toFixed(1)}</td>
                      <td>{row.market_mean.toFixed(2)}</td>
                      <td>{row.value_par.toFixed(2)}</td>
                      <td>{row.sample_size}</td>
                      <td>{row.confidence}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>
          );
        })}
      </section>
    </main>
  );
}

function MiniBoard({ rows, gapKey }: { rows: BoardRow[]; gapKey: "breakout_gap" | "trap_gap" }) {
  return (
    <table>
      <thead>
        <tr><th>Player</th><th>Pos</th><th>Actual</th><th>xPPG</th><th>Gap</th></tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={`${gapKey}-${row.player}-${row.position}`}>
            <td>{row.player}</td>
            <td>{row.position}</td>
            <td>{row.actual_ppg?.toFixed(2)}</td>
            <td>{row.neutral_xppg?.toFixed(2)}</td>
            <td className={gapKey === "breakout_gap" ? "positive" : "negative"}>{(row[gapKey] ?? 0).toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
