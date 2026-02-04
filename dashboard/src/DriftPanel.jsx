import { useEffect, useState } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { fetchDrift } from './api';

const COLORS = { normal: '#3ecf8e', medium: '#f7b731', high: '#ff6b6b' };

export default function DriftPanel() {
  const [data, setData]       = useState(null);
  const [filter, setFilter]   = useState('');   // '' | 'spend' | 'demand'
  const [error, setError]     = useState(null);

  const load = (agentType) => {
    fetchDrift(agentType || undefined)
      .then(setData)
      .catch(e => setError(e.message));
  };

  // Auto-refresh every 10 seconds
  useEffect(() => {
    load(filter);  // Initial load
    const interval = setInterval(() => load(filter), 10000);
    return () => clearInterval(interval);
  }, [filter]);

  if (error) return <p className="error-msg">{error}</p>;
  if (!data)  return <p className="loading">Loading drift data...</p>;

  const { distribution, total_anomalies, high_drift_samples } = data;

  // Pie data
  const pieData = Object.entries(distribution).map(([name, d]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: d.count,
    key: name,
  }));

  return (
    <>
      {/* Filter + cards */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 18, flexWrap: 'wrap' }}>
        {['', 'spend', 'demand'].map(v => (
          <button key={v} className={`tab-btn ${filter === v ? 'active' : ''}`} onClick={() => setFilter(v)}>
            {v || 'All'}
          </button>
        ))}
      </div>

      <div className="cards-row">
        <div className="card">
          <div className="label">Total Monitored</div>
          <div className="value blue">{pieData.reduce((s, d) => s + d.value, 0)}</div>
        </div>
        <div className="card">
          <div className="label">Anomalies</div>
          <div className="value red">{total_anomalies}</div>
        </div>
        <div className="card">
          <div className="label">Normal</div>
          <div className="value green">{distribution.normal?.count || 0}</div>
        </div>
        <div className="card">
          <div className="label">Medium Drift</div>
          <div className="value orange">{distribution.medium?.count || 0}</div>
        </div>
        <div className="card">
          <div className="label">High Drift</div>
          <div className="value red">{distribution.high?.count || 0}</div>
        </div>
      </div>

      <div className="panels-row">
        {/* Pie chart */}
        <div className="panel">
          <h3>Drift Distribution</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`} labelLine={false}>
                {pieData.map((entry) => (
                  <Cell key={entry.key} fill={COLORS[entry.key] || '#7a8fa3'} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: '#1e2736', border: '1px solid #2a3548', borderRadius: 6, color: '#c8d6e5' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* High-drift samples table */}
        <div className="panel">
          <h3>Top High-Drift Queries</h3>
          <table className="data-table">
            <thead>
              <tr><th>Query ID</th><th>Drift Score</th><th>Level</th></tr>
            </thead>
            <tbody>
              {high_drift_samples.map((s, i) => (
                <tr key={i}>
                  <td className="mono">{s.query_id}</td>
                  <td style={{ color: '#ff6b6b', fontWeight: 600 }}>{s.drift_score}</td>
                  <td><span className="badge high">{s.classification}</span></td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Avg scores per level */}
          <h3 style={{ marginTop: 18 }}>Avg Drift Score by Level</h3>
          <table className="data-table">
            <thead><tr><th>Level</th><th>Count</th><th>Avg Score</th></tr></thead>
            <tbody>
              {Object.entries(distribution).map(([lvl, d]) => (
                <tr key={lvl}>
                  <td><span className={`badge ${lvl}`}>{lvl}</span></td>
                  <td>{d.count}</td>
                  <td>{d.avg_drift_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
