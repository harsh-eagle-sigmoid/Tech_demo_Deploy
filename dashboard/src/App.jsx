import { useState, useEffect } from 'react';
import './App.css';
import { motion } from 'framer-motion';
import { LayoutDashboard, Activity, AlertTriangle, Play, Bell, ChevronLeft, ChevronRight, LogOut, ArrowLeft } from 'lucide-react';
import { fetchHealth } from './api';
import MetricsPanel from './MetricsPanel';
import DriftPanel from './DriftPanel';
import ErrorsPanel from './ErrorsPanel';
import QueryPanel from './QueryPanel';
import ExecutionsPanel from './ExecutionsPanel';
import AlertsPanel from './AlertsPanel';
import AuthProvider, { LoginButton, RequireAuth, useAuth } from './AuthProvider';
import AgentSelector from './AgentSelector';

const TABS = ['Metrics', 'Drift', 'Errors', 'Executions', 'Alerts'];

// Main Dashboard
function Dashboard({ agentId, initialTab, onBack, onTabChange }) {
  const [tab, setTab] = useState(initialTab || 'Metrics');
  const [collapsed, setCollapsed] = useState(false);
  const [health, setHealth] = useState(null);
  const { authEnabled, user } = useAuth();

  const TAB_ICONS = {
    'Metrics': <LayoutDashboard size={20} />,
    'Drift': <Activity size={20} />,
    'Errors': <AlertTriangle size={20} />,
    'Executions': <Play size={20} />,
    'Alerts': <Bell size={20} />
  };

  // Track visited tabs to lazy-load content
  const [visitedTabs, setVisitedTabs] = useState(new Set([initialTab || 'Metrics']));

  // Sync tab if initialTab changes (e.g. from state restore)
  useEffect(() => {
    if (initialTab) {
      setTab(initialTab);
      setVisitedTabs(prev => new Set(prev).add(initialTab));
    }
  }, [initialTab]);

  useEffect(() => {
    fetchHealth().then(setHealth);
    const interval = setInterval(() => fetchHealth().then(setHealth), 10000);
    return () => clearInterval(interval);
  }, []);

  const handleTabSwitch = (t) => {
    setTab(t);
    setVisitedTabs(prev => new Set(prev).add(t));
    if (onTabChange) onTabChange(t);
  };

  const agentsUp = health
    ? Object.values(health.agents || {}).every(a => a.status === 'ok')
    : false;

  return (
    <div className="app-shell">
      {/* ── Sidebar ── */}
      <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
        <div className="brand">
          <div className="logo-icon" style={{ width: 32, height: 32, background: 'linear-gradient(135deg, #4c9eff 0%, #3ecf8e 100%)', borderRadius: 8, flexShrink: 0 }}></div>
          <span className="brand-text">Unilever GenAI</span>
        </div>

        <button className="collapse-btn" onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>

        <div className="nav-links">
          {TABS.map(t => (
            <button key={t} className={`nav-item ${tab === t ? 'active' : ''}`} onClick={() => handleTabSwitch(t)} title={collapsed ? t : ''}>
              <div className="icon-wrapper">{TAB_ICONS[t]}</div>
              <span className="link-text">{t}</span>
            </button>
          ))}
        </div>

        <div style={{ marginTop: 'auto', paddingTop: 20, borderTop: '1px solid #2a3548' }}>
          {onBack && (
            <button onClick={onBack} className="nav-item" style={{ color: '#ff6b6b' }}>
              <div className="icon-wrapper"><ArrowLeft size={20} /></div>
              <span className="link-text">Switch Agent</span>
            </button>
          )}
        </div>
      </aside>

      {/* ── Main Content Area ── */}
      <div className="main-wrapper">

        {/* Top Header for User/Status */}
        <header className="top-header">
          <div>
            <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.5px' }}>
              {agentId ? (agentId.charAt(0).toUpperCase() + agentId.slice(1) + " GPT") : "Dashboard"}
            </h2>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 500 }}>Control Plane & Monitoring</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <div className="nav-status" style={{ fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 8, background: '#1e293b', padding: '6px 12px', borderRadius: 20, border: '1px solid #2a3548' }}>
              <span className={`status-dot ${agentsUp ? '' : 'down'}`} style={{ width: 8, height: 8, borderRadius: '50%', background: agentsUp ? '#3ecf8e' : '#ff6b6b', boxShadow: agentsUp ? '0 0 8px rgba(62,207,142,0.4)' : 'none' }} />
              {agentsUp ? 'System Online' : ' Issues Detected'}
            </div>
            <LoginButton />
          </div>
        </header>

        <main className="main-content">
          <div style={{ display: tab === 'Metrics' ? 'block' : 'none' }} className="tab-pane fade-in">
            {visitedTabs.has('Metrics') && <MetricsPanel agentId={agentId} isActive={tab === 'Metrics'} />}
          </div>
          <div style={{ display: tab === 'Drift' ? 'block' : 'none' }} className="tab-pane fade-in">
            {visitedTabs.has('Drift') && <DriftPanel agentId={agentId} isActive={tab === 'Drift'} />}
          </div>
          <div style={{ display: tab === 'Errors' ? 'block' : 'none' }} className="tab-pane fade-in">
            {visitedTabs.has('Errors') && <ErrorsPanel agentId={agentId} isActive={tab === 'Errors'} />}
          </div>
          <div style={{ display: tab === 'Executions' ? 'block' : 'none' }} className="tab-pane fade-in">
            {visitedTabs.has('Executions') && <ExecutionsPanel agentId={agentId} isActive={tab === 'Executions'} />}
          </div>
          <div style={{ display: tab === 'Alerts' ? 'block' : 'none' }} className="tab-pane fade-in">
            {visitedTabs.has('Alerts') && <AlertsPanel isActive={tab === 'Alerts'} />}
          </div>
        </main>
      </div>
    </div>
  );
}

// Main App with Auth Provider - RequireAuth blocks access until logged in
// Main App with Auth Provider - RequireAuth blocks access until logged in
export default function App() {
  const [selection, setSelection] = useState(() => {
    // Restore from localStorage on load
    try {
      const saved = localStorage.getItem('dashboard_selection');
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      return null;
    }
  });

  const handleSelect = (agentId, tab = 'Metrics') => {
    const s = { agentId, tab };
    setSelection(s);
    localStorage.setItem('dashboard_selection', JSON.stringify(s));
  };

  const handleTabChange = (t) => {
    if (selection) {
      handleSelect(selection.agentId, t);
    }
  };

  const handleBack = () => {
    setSelection(null);
    localStorage.removeItem('dashboard_selection');
  };

  return (
    <AuthProvider>
      <RequireAuth>
        {!selection ? (
          <AgentSelector onSelect={handleSelect} />
        ) : (
          <Dashboard
            agentId={selection.agentId}
            initialTab={selection.tab}
            onBack={handleBack}
            onTabChange={handleTabChange}
          />
        )}
      </RequireAuth>
    </AuthProvider>
  );
}
