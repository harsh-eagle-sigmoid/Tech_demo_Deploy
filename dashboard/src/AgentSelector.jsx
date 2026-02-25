import React, { useEffect, useState } from 'react';
import axios from 'axios';
import GradientText from './components/GradientText';
import FloatingLines from './components/FloatingLines';
import AnimatedContent from './components/AnimatedContent';
import { registerAgent, deleteAgent, retryGroundTruth } from './api';

import './AgentSelector.css';

const EMPTY_FORM = { agent_name: '', db_url: '', agent_url: '', display_name: '', description: '' };

export default function AgentSelector({ onSelect }) {
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [form, setForm] = useState(EMPTY_FORM);
    const [submitting, setSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState('');
    const [registrationResult, setRegistrationResult] = useState(null);
    const [copied, setCopied] = useState(false);

    const loadAgents = () => {
        const API_BASE = import.meta.env.VITE_API_URL || '';
        axios.get(`${API_BASE}/api/v1/agents/summary`)
            .then(res => { setAgents(res.data); setLoading(false); })
            .catch(err => { console.error("Failed to load agents summary", err); setLoading(false); });
    };

    useEffect(() => {
        loadAgents();
        document.body.style.animation = 'none';
        return () => { document.body.style.animation = ''; };
    }, []);

    const handleFormChange = (e) => {
        const { name, value } = e.target;
        setForm(prev => ({ ...prev, [name]: value }));
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        setSubmitError('');
        try {
            const result = await registerAgent(form);
            setRegistrationResult(result);
            setForm(EMPTY_FORM);
            setLoading(true);
            loadAgents();
        } catch (err) {
            setSubmitError(err?.response?.data?.detail || 'Registration failed.');
        } finally {
            setSubmitting(false);
        }
    };

    const handleCopyKey = () => {
        if (registrationResult?.agent?.api_key) {
            navigator.clipboard.writeText(registrationResult.agent.api_key);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    const closeModal = () => {
        setShowModal(false);
        setRegistrationResult(null);
        setSubmitError('');
        setCopied(false);
    };

    const handleDelete = async (agentId, agentName) => {
        if (!window.confirm(`Remove agent "${agentName}" from monitoring? The agent itself will not be affected.`)) return;
        try {
            await deleteAgent(agentId);
            setLoading(true);
            loadAgents();
        } catch (err) {
            alert(err?.response?.data?.detail || 'Failed to remove agent.');
        }
    };

    const handleRetryGroundTruth = async (agentId, agentName, e) => {
        e.stopPropagation();
        if (!window.confirm(`Retry ground truth generation for "${agentName}"?`)) return;
        try {
            await retryGroundTruth(agentId);
            alert('Ground truth generation retry started. This may take 1-2 minutes.');
            setLoading(true);
            loadAgents();
        } catch (err) {
            alert(err?.response?.data?.detail || 'Failed to retry ground truth generation.');
        }
    };

    if (loading) return <div style={{ color: '#fff', textAlign: 'center', marginTop: '50px' }}>Loading Control Plane...</div>;

    return (
        <div className="agent-shell">
            {/* Background Animation */}
            <div className="agent-bg-wrapper">
                <FloatingLines
                    animationSpeed={0.5}
                    bottomWavePosition={{ x: 2.0, y: -1.0, rotate: -1 }}
                    mixBlendMode="normal"
                />
            </div>

            {/* Main Content */}
            <div className="agent-selector-container">
                <AnimatedContent distance={80} direction="vertical" reverse={false} duration={3.0}
                    ease="power2.out" initialOpacity={0} animateOpacity scale={0.95} delay={0.2}>
                    <div className="agent-header">
                        <div className="agent-badge">GENAI OBSERVABILITY</div>
                        <GradientText colors={["#4c9eff", "#3ecf8e", "#a55eea"]} animationSpeed={8}
                            showBorder={false} className="text-3xl font-bold">
                            <h1 className="agent-title">Unilever GenAI Control Plane</h1>
                        </GradientText>
                        <p className="agent-subtitle">LLMOps monitoring and governance</p>
                    </div>
                </AnimatedContent>

                <div className="agent-grid">
                    {agents.map((agent, index) => (
                        <AnimatedContent key={agent.id} distance={50} direction="vertical" reverse={false}
                            duration={3.0} ease="power2.out" initialOpacity={0} animateOpacity scale={0.9}
                            delay={0.6 + (index * 0.3)}>
                            <div className="agent-card">
                                <div className="agent-card-header">
                                    <div>
                                        <h3 className="agent-card-title">{agent.name}</h3>
                                        <p className="agent-card-desc">{agent.description}</p>
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <span className={`agent-status-badge ${
                                            agent.status === 'Healthy' ? 'status-healthy' :
                                            agent.status === 'Unhealthy' ? 'status-unhealthy' :
                                            agent.status === 'SDK Issue' ? 'status-sdk-issue' :
                                            agent.status === 'Degraded' ? 'status-issue' :
                                            'status-unknown'
                                        }`}>
                                            {agent.status}
                                        </span>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleDelete(agent.agent_id || agent.id, agent.name); }}
                                            title="Remove Agent"
                                            style={{
                                                background: 'transparent', border: '1px solid #2a3548', borderRadius: '4px',
                                                color: '#ff6b6b', cursor: 'pointer', fontSize: '14px', padding: '2px 6px',
                                                lineHeight: 1, opacity: 0.6, transition: 'opacity 0.2s'
                                            }}
                                            onMouseEnter={(e) => e.target.style.opacity = 1}
                                            onMouseLeave={(e) => e.target.style.opacity = 0.6}
                                        >
                                            &times;
                                        </button>
                                    </div>
                                </div>

                                <div className="agent-metrics">
                                    <div>
                                        <div className="metric-label">Agent Accuracy</div>
                                        <div className="metric-value-lg">{agent.accuracy}%</div>
                                    </div>
                                    <div className="accuracy-visual">
                                        <div className="accuracy-dot"></div>
                                    </div>
                                </div>

                                <div className="agent-stats-row">
                                    <div>
                                        <div className="stat-label">Requests (24h)</div>
                                        <div className="stat-value">{agent.requests}</div>
                                    </div>
                                    <div>
                                        <div className="stat-label">Avg Latency</div>
                                        <div className="stat-value">{agent.latency_s}s</div>
                                    </div>
                                </div>

                                {/* Ground Truth Status */}
                                <div className="agent-stats-row" style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(42, 53, 72, 0.5)' }}>
                                    <div style={{ flex: 1 }}>
                                        <div className="stat-label">Ground Truth</div>
                                        <div style={{ marginTop: '4px' }}>
                                            {agent.gt_status === 'success' && (
                                                <div className="stat-value" style={{ color: '#3ecf8e', fontSize: '14px' }}>
                                                    ✓ {agent.gt_query_count} queries
                                                </div>
                                            )}
                                            {agent.gt_status === 'failed' && (
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                    <span className="stat-value" style={{ color: '#ff6b6b', fontSize: '13px' }}>
                                                        ✗ Failed
                                                    </span>
                                                    <button
                                                        onClick={(e) => handleRetryGroundTruth(agent.agent_id, agent.name, e)}
                                                        style={{
                                                            background: 'rgba(76, 158, 255, 0.1)',
                                                            border: '1px solid rgba(76, 158, 255, 0.3)',
                                                            borderRadius: '3px',
                                                            color: '#4c9eff',
                                                            cursor: 'pointer',
                                                            fontSize: '10px',
                                                            padding: '2px 6px',
                                                            fontWeight: '500',
                                                            transition: 'all 0.2s'
                                                        }}
                                                        onMouseEnter={(e) => {
                                                            e.target.style.background = 'rgba(76, 158, 255, 0.2)';
                                                        }}
                                                        onMouseLeave={(e) => {
                                                            e.target.style.background = 'rgba(76, 158, 255, 0.1)';
                                                        }}
                                                    >
                                                        Retry
                                                    </button>
                                                </div>
                                            )}
                                            {agent.gt_status === 'in_progress' && (
                                                <div className="stat-value" style={{ color: '#ffc107', fontSize: '13px' }}>
                                                    ⟳ Generating...
                                                </div>
                                            )}
                                            {agent.gt_status === 'pending' && (
                                                <div className="stat-value" style={{ color: '#94a3b8', fontSize: '13px' }}>
                                                    Pending
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                    {agent.gt_retry_count > 0 && (
                                        <div>
                                            <div className="stat-label">Retries</div>
                                            <div className="stat-value">{agent.gt_retry_count}</div>
                                        </div>
                                    )}
                                </div>

                                <button onClick={() => setTimeout(() => onSelect({ id: agent.id, numericId: agent.agent_id }), 150)} className="agent-select-btn">
                                    Open Control Plane &rarr;
                                </button>
                            </div>
                        </AnimatedContent>
                    ))}

                    {/* Register New Agent card */}
                    <AnimatedContent distance={50} direction="vertical" reverse={false} duration={3.0}
                        ease="power2.out" initialOpacity={0} animateOpacity scale={0.9}
                        delay={0.6 + (agents.length * 0.3)}>
                        <div className="agent-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px', cursor: 'pointer', border: '2px dashed #2a3548' }}
                            onClick={() => setShowModal(true)}>
                            <div style={{ fontSize: '2.5rem', color: '#4c9eff' }}>+</div>
                            <div style={{ color: '#94a3b8', fontWeight: 600 }}>Register New Agent</div>
                            <div style={{ color: '#5a7a99', fontSize: '12px', textAlign: 'center' }}>
                                Connect any PostgreSQL-backed agent via DB URL
                            </div>
                        </div>
                    </AnimatedContent>
                </div>

                {/* Footer */}
                <div className="agent-footer">
                    <p style={{ margin: 0 }}>© 2024 Unilever Procurement GenAI. Internal Use Only.</p>
                    <p style={{ margin: '5px 0 0 0', fontSize: '11px' }}>v2.0.0 • Connected to Local Cluster</p>
                </div>
            </div>

            {/* Register Agent Modal */}
            {showModal && (
                <div style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
                }}>
                    <div style={{
                        background: '#1e2736', border: '1px solid #2a3548', borderRadius: '12px',
                        padding: '32px', width: '520px', maxWidth: '90vw', maxHeight: '90vh', overflowY: 'auto'
                    }}>
                        {registrationResult ? (
                            /* ── Success Panel ── */
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                <h2 style={{ color: '#3ecf8e', fontSize: '18px', margin: 0 }}>Agent Registered Successfully</h2>

                                <div style={{ background: '#0d1117', border: '1px solid #2a3548', borderRadius: '8px', padding: '16px' }}>
                                    <div style={{ color: '#ff6b6b', fontSize: '12px', fontWeight: 600, marginBottom: '8px' }}>
                                        Save your API key now — it will not be shown again.
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <code style={{
                                            flex: 1, color: '#4c9eff', fontSize: '13px', wordBreak: 'break-all',
                                            background: '#161b22', padding: '8px', borderRadius: '4px'
                                        }}>
                                            {registrationResult.agent?.api_key}
                                        </code>
                                        <button onClick={handleCopyKey} style={{
                                            padding: '6px 14px', background: copied ? '#3ecf8e' : '#4c9eff',
                                            border: 'none', borderRadius: '6px', color: '#fff', cursor: 'pointer',
                                            fontSize: '12px', whiteSpace: 'nowrap'
                                        }}>
                                            {copied ? 'Copied!' : 'Copy'}
                                        </button>
                                    </div>
                                </div>

                                <div style={{ background: '#0d1117', border: '1px solid #2a3548', borderRadius: '8px', padding: '16px' }}>
                                    <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: 600, marginBottom: '8px' }}>Install SDK</div>
                                    <code style={{ color: '#3ecf8e', fontSize: '13px' }}>{registrationResult.sdk_install}</code>
                                </div>

                                <div style={{ background: '#0d1117', border: '1px solid #2a3548', borderRadius: '8px', padding: '16px' }}>
                                    <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: 600, marginBottom: '8px' }}>Add to your agent (2 lines)</div>
                                    <pre style={{
                                        color: '#c8d6e5', fontSize: '12px', margin: 0, whiteSpace: 'pre-wrap',
                                        lineHeight: 1.5
                                    }}>
{registrationResult.sdk_snippet}
                                    </pre>
                                </div>

                                <button onClick={closeModal} style={{
                                    padding: '10px 18px', background: '#4c9eff', border: 'none',
                                    borderRadius: '6px', color: '#fff', cursor: 'pointer', alignSelf: 'flex-end'
                                }}>
                                    Done
                                </button>
                            </div>
                        ) : (
                            /* ── Registration Form ── */
                            <>
                                <h2 style={{ color: '#c8d6e5', marginBottom: '20px', fontSize: '18px' }}>Register New Agent</h2>
                                <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                                    {[
                                        { label: 'Agent Name *', name: 'agent_name', placeholder: 'e.g. procurement', required: true },
                                        { label: 'Database URL *', name: 'db_url', placeholder: 'postgresql://user:pass@host:5432/dbname', required: true },
                                        { label: 'Agent URL', name: 'agent_url', placeholder: 'http://localhost:8001 (optional)' },
                                        { label: 'Display Name', name: 'display_name', placeholder: 'Procurement GPT' },
                                        { label: 'Description', name: 'description', placeholder: 'Short description' },
                                    ].map(({ label, name, placeholder, required }) => (
                                        <div key={name}>
                                            <label style={{ color: '#94a3b8', fontSize: '12px', display: 'block', marginBottom: '4px' }}>{label}</label>
                                            <input
                                                name={name} value={form[name]} onChange={handleFormChange}
                                                placeholder={placeholder} required={required}
                                                style={{
                                                    width: '100%', padding: '8px 10px', background: '#0d1117',
                                                    border: '1px solid #2a3548', borderRadius: '6px', color: '#c8d6e5',
                                                    fontSize: '13px', boxSizing: 'border-box'
                                                }}
                                            />
                                        </div>
                                    ))}
                                    <div style={{ color: '#5a7a99', fontSize: '11px', marginTop: '-4px' }}>
                                        An API key will be generated for SDK access.
                                    </div>
                                    {submitError && <div style={{ color: '#ff6b6b', fontSize: '12px' }}>{submitError}</div>}
                                    <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
                                        <button type="button" onClick={closeModal}
                                            style={{ padding: '8px 18px', background: 'transparent', border: '1px solid #2a3548', borderRadius: '6px', color: '#94a3b8', cursor: 'pointer' }}>
                                            Cancel
                                        </button>
                                        <button type="submit" disabled={submitting}
                                            style={{ padding: '8px 18px', background: '#4c9eff', border: 'none', borderRadius: '6px', color: '#fff', cursor: 'pointer', opacity: submitting ? 0.7 : 1 }}>
                                            {submitting ? 'Registering...' : 'Register Agent'}
                                        </button>
                                    </div>
                                </form>
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
