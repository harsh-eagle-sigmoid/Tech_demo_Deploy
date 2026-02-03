import { useState, useEffect } from 'react';
import './App.css';
import { fetchHealth }  from './api';
import MetricsPanel     from './MetricsPanel';
import DriftPanel       from './DriftPanel';
import ErrorsPanel      from './ErrorsPanel';
import QueryPanel       from './QueryPanel';

const TABS = ['Metrics', 'Drift', 'Errors', 'Query'];

export default function App() {
  const [tab,    setTab]    = useState('Metrics');
  const [health, setHealth] = useState(null);

  // Poll health every 10 s
  useEffect(() => {
    const poll = () => fetchHealth().then(setHealth).catch(() => {});
    poll();
    const id = setInterval(poll, 10_000);
    return () => clearInterval(id);
  }, []);

  const agentsUp = health
    ? Object.values(health.agents || {}).every(a => a.status === 'ok')
    : false;

  return (
    <div className="app-shell">
      {/* ── Navbar ── */}
      <nav className="navbar">
        <div className="brand">Unilever <span>Procurement GPT</span> — POC</div>
        <div className="tabs">
          {TABS.map(t => (
            <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </div>
        <div className="nav-status">
          <span className={`status-dot ${agentsUp ? '' : 'down'}`} />
          {agentsUp ? 'All agents online' : 'Checking…'}
        </div>
      </nav>

      {/* ── Panel ── */}
      <main className="main-content">
        {tab === 'Metrics' && <MetricsPanel />}
        {tab === 'Drift'  && <DriftPanel  />}
        {tab === 'Errors' && <ErrorsPanel />}
        {tab === 'Query'  && <QueryPanel  />}
      </main>
    </div>
  );
}
