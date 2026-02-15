import React, { useEffect, useState } from 'react';
import axios from 'axios';
import GradientText from './components/GradientText';
import FloatingLines from './components/FloatingLines';
import AnimatedContent from './components/AnimatedContent';

import './AgentSelector.css';

export default function AgentSelector({ onSelect }) {
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        axios.get(`${API_BASE}/api/v1/agents/summary`)
            .then(res => {
                setAgents(res.data);
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to load agents summary", err);
                setLoading(false);
            });

        // Disable body animation to save GPU
        document.body.style.animation = 'none';

        return () => {
            document.body.style.animation = ''; // restore
        };
    }, []);

    if (loading) return <div style={{ color: '#fff', textAlign: 'center', marginTop: '50px' }}>Loading Control Plane...</div>;

    return (
        <div className="agent-shell">
            {/* Background Animation */}
            <div className="agent-bg-wrapper">
                <FloatingLines
                    animationSpeed={0.5}
                    bottomWavePosition={{ x: 2.0, y: -1.0, rotate: -1 }}
                    mixBlendMode="normal" // Critical for performance
                />
            </div>

            {/* Main Content */}
            <div className="agent-selector-container">
                <AnimatedContent
                    distance={80}
                    direction="vertical"
                    reverse={false}
                    duration={3.0}
                    ease="power2.out"
                    initialOpacity={0}
                    animateOpacity
                    scale={0.95}
                    delay={0.2}
                >
                    <div className="agent-header">
                        <div className="agent-badge">
                            GENAI OBSERVABILITY
                        </div>
                        <GradientText
                            colors={["#4c9eff", "#3ecf8e", "#a55eea"]}
                            animationSpeed={8}
                            showBorder={false}
                            className="text-3xl font-bold"
                        >
                            <h1 className="agent-title">Unilever GenAI Control Plane</h1>
                        </GradientText>
                        <p className="agent-subtitle">LLMOps monitoring and governance</p>
                    </div>
                </AnimatedContent>

                <div className="agent-grid">
                    {agents.map((agent, index) => (
                        <AnimatedContent
                            key={agent.id}
                            distance={50}
                            direction="vertical"
                            reverse={false}
                            duration={3.0}
                            ease="power2.out"
                            initialOpacity={0}
                            animateOpacity
                            scale={0.9}
                            delay={0.6 + (index * 0.3)} // Staggered Delay
                        >
                            <div className="agent-card">
                                <div className="agent-card-header">
                                    <div>
                                        <h3 className="agent-card-title">{agent.name}</h3>
                                        <p className="agent-card-desc">{agent.description}</p>
                                    </div>
                                    <span className={`agent-status-badge ${agent.status === 'Healthy' ? 'status-healthy' : 'status-issue'}`}>
                                        {agent.status}
                                    </span>
                                </div>

                                <div className="agent-metrics">
                                    <div>
                                        <div className="metric-label">Agent Accuracy</div>
                                        <div className="metric-value-lg">
                                            {agent.accuracy}%
                                        </div>
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

                                <button
                                    onClick={() => {
                                        // Small delay to allow button animation to play and prevent "lag" feel
                                        setTimeout(() => onSelect(agent.id), 150);
                                    }}
                                    className="agent-select-btn"
                                >
                                    Open Control Plane &rarr;
                                </button>
                            </div>
                        </AnimatedContent>
                    ))}
                </div>

                {/* Footer */}
                <div className="agent-footer">
                    <p style={{ margin: 0 }}>© 2024 Unilever Procurement GenAI. Internal Use Only.</p>
                    <p style={{ margin: '5px 0 0 0', fontSize: '11px' }}>v2.0.0 • Connected to Local Cluster</p>
                </div>
            </div>
        </div>
    );
}
