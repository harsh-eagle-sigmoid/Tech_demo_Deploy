# Data Quality Components Integration Guide

This guide shows how to integrate the Data Quality components into your dashboard.

## Components Available

1. **DataQualityPanel** - Full panel showing all issues with details
2. **DataQualityBadge** - Compact badge for agent lists

---

## 1. Add to Agent Detail Page

```jsx
// Example: AgentDetail.jsx
import React from 'react';
import DataQualityPanel from './DataQualityPanel';

function AgentDetail({ agentId }) {
  return (
    <div className="agent-detail">
      <h1>Agent Details</h1>

      {/* Other agent info... */}

      {/* Add Data Quality Panel */}
      <DataQualityPanel agentId={agentId} agentName="Marketing Agent" />
    </div>
  );
}
```

---

## 2. Add Badge to Agent List

```jsx
// Example: AgentList.jsx
import React from 'react';
import DataQualityBadge from './DataQualityBadge';

function AgentList({ agents }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Status</th>
          <th>Data Quality</th>
        </tr>
      </thead>
      <tbody>
        {agents.map(agent => (
          <tr key={agent.id}>
            <td>{agent.name}</td>
            <td>{agent.status}</td>
            <td>
              {/* Add compact badge */}
              <DataQualityBadge agentId={agent.id} compact={false} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

---

## 3. Add to Agent Summary Cards

```jsx
// Example: AgentCard.jsx
import React from 'react';
import DataQualityBadge from './DataQualityBadge';

function AgentCard({ agent }) {
  return (
    <div className="agent-card">
      <h3>{agent.name}</h3>
      <p>{agent.description}</p>

      <div className="agent-badges">
        <span className="status-badge">{agent.status}</span>
        {/* Add compact icon badge */}
        <DataQualityBadge agentId={agent.id} compact={true} />
      </div>
    </div>
  );
}
```

---

## 4. Add Tab in Agent Dashboard

```jsx
// Example: AgentDashboard.jsx
import React, { useState } from 'react';
import DataQualityPanel from './DataQualityPanel';

function AgentDashboard({ agentId }) {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <div className="agent-dashboard">
      <div className="tabs">
        <button onClick={() => setActiveTab('overview')}>Overview</button>
        <button onClick={() => setActiveTab('queries')}>Queries</button>
        <button onClick={() => setActiveTab('data-quality')}>Data Quality</button>
      </div>

      <div className="tab-content">
        {activeTab === 'overview' && <OverviewPanel agentId={agentId} />}
        {activeTab === 'queries' && <QueriesPanel agentId={agentId} />}
        {activeTab === 'data-quality' && (
          <DataQualityPanel agentId={agentId} agentName="My Agent" />
        )}
      </div>
    </div>
  );
}
```

---

## 5. Standalone Page

```jsx
// Example: DataQualityPage.jsx
import React from 'react';
import { useParams } from 'react-router-dom';
import DataQualityPanel from './DataQualityPanel';

function DataQualityPage() {
  const { agentId } = useParams();

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Data Quality Validation</h1>
        <p>View and manage data quality issues for your agents</p>
      </div>

      <DataQualityPanel agentId={agentId} />
    </div>
  );
}

export default DataQualityPage;
```

---

## Component Props

### DataQualityPanel

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `agentId` | number | Yes | Agent ID to fetch issues for |
| `agentName` | string | No | Agent name to display in header |

### DataQualityBadge

| Prop | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `agentId` | number | Yes | - | Agent ID to fetch summary for |
| `compact` | boolean | No | false | Show compact icon-only badge |

---

## API Endpoints Used

```
GET  /api/v1/agents/{agentId}/data-quality  - Fetch issues
POST /api/v1/agents/{agentId}/revalidate    - Trigger validation
```

---

## Example Response

```json
{
  "agent_id": 39,
  "total_issues": 2,
  "critical": 0,
  "warnings": 2,
  "info": 0,
  "issues": [
    {
      "issue_id": 1,
      "agent_id": 39,
      "schema_name": "marketing_data",
      "table_name": "campaigns",
      "column_name": null,
      "issue_type": "missing_primary_key",
      "severity": "warning",
      "message": "Table marketing_data.campaigns has no primary key",
      "affected_rows": null,
      "total_rows": null,
      "percentage": null,
      "status": "open",
      "discovered_at": "2026-02-23T21:37:58.802562"
    }
  ]
}
```

---

## Styling

Both components come with CSS files that should be imported automatically. If you need to customize:

- `DataQualityPanel.css` - Full panel styles
- `DataQualityBadge.css` - Badge styles

You can override styles in your own CSS files.

---

## Features

### DataQualityPanel

- ✅ Summary cards with severity breakdown
- ✅ Filterable issues list (All, Critical, Warning, Info)
- ✅ Expandable issue details
- ✅ Manual revalidation trigger
- ✅ Loading and error states
- ✅ Responsive design

### DataQualityBadge

- ✅ Color-coded severity
- ✅ Compact and full modes
- ✅ Hover tooltips
- ✅ Auto-refresh support

---

## Testing

```jsx
import DataQualityPanel from './DataQualityPanel';

// Test with mock agent ID
<DataQualityPanel agentId={39} agentName="Test Agent" />
```

Make sure the API is running at `http://localhost:8000` and the agent exists.
