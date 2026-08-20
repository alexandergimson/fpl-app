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

function App() {
  const [points, setPoints] = useState<ParPoint[]>([]);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/price-par")
      .then((response) => response.json())
      .then(setPoints)
      .catch(() => setPoints([]));
  }, []);

  const positions = [...new Set(points.map((point) => point.position))];

  return (
    <main>
      <header>
        <h1>FPL Analytics</h1>
        <p>Price Par curves by position and current price.</p>
      </header>
      <section className="grid">
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

createRoot(document.getElementById("root")!).render(<App />);
