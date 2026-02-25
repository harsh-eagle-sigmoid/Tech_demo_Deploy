import { useEffect, useState } from 'react';
import { BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Activity, CheckCircle, AlertTriangle, Target, Trophy, Clock } from 'lucide-react';
import { fetchMetrics } from './api';
import RecentQueriesPanel from './RecentQueriesPanel';

export default function MetricsPanel({ agentId, isActive = true }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    if (!isActive) return;
    const load = () => fetchMetrics(agentId).then(setData).catch(e => setError(e.message));
    load();  // Initial load
    const interval = setInterval(load, 3000);  // Poll every 3s
    return () => clearInterval(interval);
  }, [agentId, isActive]);

  if (error) return <p className="error-msg">{error}</p>;
  if (!data) return <p className="loading">Loading metrics...</p>;

  const { overall, per_agent } = data;

  // Bar chart data: one bar per agent
  const chartData = Object.entries(per_agent).map(([name, d]) => ({
    agent: name.charAt(0).toUpperCase() + name.slice(1),
    Accuracy: d.accuracy,
    AvgScore: +(d.avg_score * 100).toFixed(1),
  }));

  // Dynamic agent keys from trend data (exclude 'time')
  const AGENT_COLORS = ['#4c9eff', '#3ecf8e', '#a55eea', '#ff9f43', '#ff6b6b', '#ffd43b'];
  const agentKeys = data.trend && data.trend.length > 0
    ? Object.keys(data.trend[0]).filter(k => k !== 'time')
    : [];
  // SVG IDs cannot contain spaces — sanitize agent names for gradient IDs
  const safeId = (key) => key.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_-]/g, '');

  return (
    <>
      {/* Stat cards */}
      <div className="cards-row metrics-overview">
        <div className="card">
          <div className="label" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={16} color="#4c9eff" /> Total Evaluated
          </div>
          <div className="value blue">{overall.total_evaluations}</div>
        </div>
        <div className="card">
          <div className="label" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle size={16} color="#3ecf8e" /> Passed
          </div>
          <div className="value green">{overall.passed}</div>
        </div>
        <div className="card">
          <div className="label" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} color="#ff6b6b" /> Failed
          </div>
          <div className="value red">{overall.failed}</div>
        </div>
        <div className="card">
          <div className="label" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Target size={16} color={overall.accuracy >= 90 ? "#3ecf8e" : "#f7b731"} /> Accuracy
          </div>
          <div className={`value ${overall.accuracy >= 90 ? 'green' : 'orange'}`}>{overall.accuracy}%</div>
        </div>
        <div className="card">
          <div className="label" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Trophy size={16} color="#4c9eff" /> Avg Score
          </div>
          <div className="value blue">{overall.avg_score}</div>
        </div>
        <div className="card">
          <div className="label" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={16} color="#a55eea" /> Avg Latency
          </div>
          <div className="value purple">{overall.avg_latency} ms</div>
        </div>
      </div>

      {/* Chart + per-agent table */}
      <div className="panels-row">
        <div className="panel">
          <h3>Accuracy Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={data.trend || []}>
              <defs>
                {agentKeys.map((key, i) => (
                  <linearGradient key={key} id={`color_${safeId(key)}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={AGENT_COLORS[i % AGENT_COLORS.length]} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={AGENT_COLORS[i % AGENT_COLORS.length]} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" />
              <XAxis dataKey="time" stroke="#5a7a99" fontSize={12} />
              <YAxis domain={[0, 100]} stroke="#5a7a99" fontSize={12} unit="%" />
              <Tooltip contentStyle={{ background: '#1e2736', border: '1px solid #2a3548', borderRadius: 6, color: '#c8d6e5' }} />
              {agentKeys.map((key, i) => (
                <Area key={key} type="monotone" dataKey={key}
                  stroke={AGENT_COLORS[i % AGENT_COLORS.length]} strokeWidth={2}
                  fillOpacity={1} fill={`url(#color_${safeId(key)})`} activeDot={{ r: 6 }} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="panel">
          <h3>Accuracy by Agent</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} barGap={4}>
              <defs>
                <linearGradient id="barGradientAccuracy" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#4c9eff" stopOpacity={1} />
                  <stop offset="100%" stopColor="#8c52ff" stopOpacity={1} />
                </linearGradient>
                <linearGradient id="barGradientScore" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3ecf8e" stopOpacity={1} />
                  <stop offset="100%" stopColor="#2ea043" stopOpacity={1} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" />
              <XAxis dataKey="agent" stroke="#5a7a99" fontSize={13} />
              <YAxis domain={[0, 100]} stroke="#5a7a99" fontSize={12} unit="%" />
              <Tooltip contentStyle={{ background: '#1e2736', border: '1px solid #2a3548', borderRadius: 6, color: '#c8d6e5' }} />
              <Legend wrapperStyle={{ color: '#94a3b8', fontSize: 12 }} />
              <Bar dataKey="Accuracy" fill="url(#barGradientAccuracy)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="AvgScore" fill="url(#barGradientScore)" radius={[4, 4, 0, 0]} name="Avg Score %" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="panel" style={{ gridColumn: '1 / -1' }}>
          <h3>Per-Agent Breakdown</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Total</th>
                <th>Passed</th>
                <th>Accuracy</th>
                <th>Avg Score</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(per_agent).map(([name, d]) => (
                <tr key={name}>
                  <td style={{ textTransform: 'capitalize', fontWeight: 600, color: '#fff' }}>{name}</td>
                  <td>{d.total}</td>
                  <td style={{ color: '#3ecf8e' }}>{d.passed}</td>
                  <td><span className={`badge ${d.accuracy >= 90 ? 'low' : 'medium'}`}>{d.accuracy}%</span></td>
                  <td>{d.avg_score}</td>
                  <td>{d.avg_latency} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent Queries Panel */}
      <RecentQueriesPanel agentId={agentId} isActive={isActive} />
    </>
  );
}
