import React, { useState, useEffect } from 'react';
import DataQualityPanel from './DataQualityPanel';
import DataQualityBadge from './DataQualityBadge';
import './DataQualityDemo.css';

/**
 * Demo page showing Data Quality components in action
 */
const DataQualityDemo = () => {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAgents();
  }, []);

  const fetchAgents = async () => {
    try {
      const response = await fetch('/api/v1/agents/summary');
      const data = await response.json();
      setAgents(data);

      // Auto-select first agent
      if (data.length > 0) {
        setSelectedAgent(data[0].agent_id);
      }
    } catch (err) {
      console.error('Error fetching agents:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="dq-demo-loading">
        <div className="spinner"></div>
        <p>Loading agents...</p>
      </div>
    );
  }

  return (
    <div className="dq-demo">
      {/* Header */}
      <div className="demo-header">
        <div className="header-content">
          <h1>🔍 Data Quality Validation</h1>
          <p>Monitor and manage data quality issues across all your agents</p>
        </div>
      </div>

      {/* Agent Selector */}
      <div className="agent-selector-section">
        <h2>Select an Agent</h2>
        <div className="agent-cards-grid">
          {agents.map(agent => (
            <div
              key={agent.agent_id}
              className={`agent-card ${selectedAgent === agent.agent_id ? 'selected' : ''}`}
              onClick={() => setSelectedAgent(agent.agent_id)}
            >
              <div className="card-header">
                <h3>{agent.name}</h3>
                <DataQualityBadge agentId={agent.agent_id} compact={true} />
              </div>
              <p className="card-description">{agent.description}</p>
              <div className="card-footer">
                <span className={`status-badge ${agent.status.toLowerCase()}`}>
                  {agent.status}
                </span>
                <span className="requests-count">
                  {agent.requests} requests
                </span>
              </div>
              <div className="card-dq-badge">
                <DataQualityBadge agentId={agent.agent_id} compact={false} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Data Quality Panel */}
      {selectedAgent && (
        <div className="dq-panel-section">
          <DataQualityPanel
            agentId={selectedAgent}
            agentName={agents.find(a => a.agent_id === selectedAgent)?.name}
          />
        </div>
      )}

      {/* Feature Highlights */}
      <div className="features-section">
        <h2>✨ Features</h2>
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">🔍</div>
            <h3>Comprehensive Validation</h3>
            <p>Checks for missing PKs, NULL values, duplicates, and more</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🗄️</div>
            <h3>Multi-Database Support</h3>
            <p>Works with PostgreSQL, MySQL, MongoDB, SQLite</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">⚡</div>
            <h3>Automatic Detection</h3>
            <p>Validates during agent onboarding automatically</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🎨</div>
            <h3>Beautiful UI</h3>
            <p>Intuitive interface with color-coded severity levels</p>
          </div>
        </div>
      </div>

      {/* API Info */}
      <div className="api-info-section">
        <h2>📡 API Endpoints</h2>
        <div className="api-cards">
          <div className="api-card">
            <code className="api-method get">GET</code>
            <code className="api-path">/api/v1/agents/{'{agent_id}'}/data-quality</code>
            <p>Fetch data quality issues for an agent</p>
          </div>
          <div className="api-card">
            <code className="api-method post">POST</code>
            <code className="api-path">/api/v1/agents/{'{agent_id}'}/revalidate</code>
            <p>Trigger manual revalidation of agent database</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataQualityDemo;
