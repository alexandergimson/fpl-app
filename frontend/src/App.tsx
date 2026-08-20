import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
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
  player: string;
  team: string;
  position: string;
  current_price: number;
  value_par: number;
  actual_ppg: number;
  neutral_xppg: number;
  next_6_xppg: number;
  buy_delta_6: number;
  expected_minutes: number;
  minutes_confidence: string;
  fixture_factor_6: number;
  status: string;
  breakout_gap?: number;
  trap_gap?: number;
};

function App() {
  const [points, setPoints] = useState<ParPoint[]>([]);
  const [board, setBoard] = useState<BoardRow[]>([]);
  const [breakouts, setBreakouts] = useState<BoardRow[]>([]);
  const [traps, setTraps] = useState<BoardRow[]>([]);
  const [tracked, setTracked] = useState<BoardRow[]>([]);

  useEffect(() => {
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
  }, []);

  const positions = [...new Set(points.map((point) => point.position))];

  return (
    <main>
      <header>
        <h1>FPL Analytics</h1>
        <p>Price Par curves by position and current price.</p>
      </header>
      <section className="grid">
        <article className="wide">
          <h2>Buy Board</h2>
          <table>
            <thead>
              <tr><th>Player</th><th>Pos</th><th>Price</th><th>Par</th><th>Next 6</th><th>Delta</th><th>Fix</th><th>Min</th><th>Conf</th><th>Status</th></tr>
            </thead>
            <tbody>
              {board.map((row) => (
                <tr key={`${row.player}-${row.position}`}>
                  <td>{row.player}</td>
                  <td>{row.position}</td>
                  <td>£{row.current_price.toFixed(1)}</td>
                  <td>{row.value_par.toFixed(2)}</td>
                  <td>{row.next_6_xppg.toFixed(2)}</td>
                  <td className={row.buy_delta_6 >= 0 ? "positive" : "negative"}>{row.buy_delta_6.toFixed(2)}</td>
                  <td>{row.fixture_factor_6.toFixed(2)}</td>
                  <td>{row.expected_minutes.toFixed(0)}</td>
                  <td>{row.minutes_confidence}</td>
                  <td>{row.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
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
              <tr><th>Player</th><th>Pos</th><th>Price</th><th>Par</th><th>Next 6</th><th>Delta</th><th>Status</th></tr>
            </thead>
            <tbody>
              {tracked.map((row) => (
                <tr key={`tracked-${row.player}-${row.position}`}>
                  <td>{row.player}</td>
                  <td>{row.position}</td>
                  <td>£{row.current_price.toFixed(1)}</td>
                  <td>{row.value_par.toFixed(2)}</td>
                  <td>{row.next_6_xppg.toFixed(2)}</td>
                  <td className={row.buy_delta_6 >= 0 ? "positive" : "negative"}>{row.buy_delta_6.toFixed(2)}</td>
                  <td>{row.status}</td>
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
