import { useState, useEffect } from 'react';
import { fetchAlerts } from './api';
import { AlertTriangle, Info, CheckCircle, XCircle } from 'lucide-react';
import './AlertsPanel.css';

const AlertsPanel = ({ isActive = true }) => {
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState('Active'); // Active, History

    useEffect(() => {
        if (!isActive) return;
        loadAlerts();
        const interval = setInterval(loadAlerts, 5000); // 5s refresh
        return () => clearInterval(interval);
    }, [isActive]);

    const loadAlerts = () => {
        fetchAlerts().then(data => {
            setAlerts(data);
            setLoading(false);
        }).catch(err => {
            console.error("Failed to load alerts", err);
            setLoading(false);
        });
    };

    // Derived Stats
    const criticalCount = alerts.filter(a => a.severity === 'critical').length;
    const warningCount = alerts.filter(a => a.severity === 'warning').length;
    const infoCount = alerts.filter(a => a.severity === 'info').length;

    const filteredAlerts = alerts; // Active Only for MVP

    if (loading && alerts.length === 0) return <div className="p-4" style={{ color: '#94a3b8' }}>Loading alerts...</div>;

    return (
        <div className="alerts-panel">
            <div className="alerts-header">
                <h2 style={{ margin: 0, fontSize: '1.2rem' }}>Alerts</h2>
                <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>Quality signal alerts — governance events requiring attention for Procurement GPT</p>
            </div>

            {/* KPI Cards */}
            <div className="kpi-grid">
                <KPICard title="Critical" count={criticalCount} color="red" icon={<XCircle size={20} />} />
                <KPICard title="Warning" count={warningCount} color="yellow" icon={<AlertTriangle size={20} />} />
                <KPICard title="Info" count={infoCount} color="blue" icon={<Info size={20} />} />
            </div>

            {/* Tabs */}
            <div className="tabs-container">
                <button
                    onClick={() => setTab('Active')}
                    className={`tab-button ${tab === 'Active' ? 'active' : ''}`}
                >
                    Active <span className="badge">{alerts.length}</span>
                </button>
                <button
                    onClick={() => setTab('History')}
                    className={`tab-button ${tab === 'History' ? 'active' : ''}`}
                >
                    History
                </button>
            </div>

            {/* Alert List */}
            <div className="alerts-list">
                {filteredAlerts.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280', border: '1px dashed #374151', borderRadius: '0.5rem' }}>
                        <CheckCircle size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
                        <p>No active alerts. System healthy.</p>
                    </div>
                ) : (
                    filteredAlerts.map(alert => (
                        <AlertCard key={alert.id} alert={alert} />
                    ))
                )}
            </div>
        </div>
    );
};

const KPICard = ({ title, count, color, icon }) => {
    return (
        <div className={`kpi-card ${color}`}>
            <div className="kpi-title">{title}</div>
            <div className="kpi-value">
                <span className="kpi-icon">{icon}</span>
                <span className="kpi-number">{count}</span>
            </div>
        </div>
    );
};

const AlertCard = ({ alert }) => {
    const icon = alert.severity === 'critical' ? <XCircle size={20} color="#ff6b6b" /> :
        alert.severity === 'warning' ? <AlertTriangle size={20} color="#f7b731" /> :
            <Info size={20} color="#4c9eff" />;

    return (
        <div className={`alert-card ${alert.severity}`}>
            <div className="alert-header">
                <div className="alert-title-row">
                    <span className="alert-icon">{icon}</span>
                    <div>
                        <h3 className="alert-title">{alert.title}</h3>
                        <p className="alert-message">{alert.message}</p>
                    </div>
                </div>
                <span className={`severity-tag ${alert.severity}`}>
                    {alert.severity}
                </span>
            </div>

            {/* Reason Box */}
            <div className="reason-box">
                <div className="reason-label">Why this alert fired:</div>
                {alert.reason}
            </div>

            <div className="alert-footer">
                <span className="timestamp">{new Date(alert.timestamp).toLocaleString()}</span>
                <button className="acknowledge-btn">
                    <CheckCircle size={14} style={{ marginRight: 4 }} /> Acknowledge
                </button>
            </div>
        </div>
    );
};

export default AlertsPanel;
