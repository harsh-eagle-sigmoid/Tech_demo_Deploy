-- Migration: Add data quality validation table
-- Description: Store validation issues found during schema discovery

CREATE TABLE IF NOT EXISTS platform.data_quality_issues (
    issue_id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES platform.agents(agent_id) ON DELETE CASCADE,

    -- Issue Location
    schema_name VARCHAR(100),
    table_name VARCHAR(100),
    column_name VARCHAR(100),  -- NULL if table-level issue

    -- Issue Details
    issue_type VARCHAR(50),  -- 'null_values', 'duplicates', 'missing_pk', etc.
    severity VARCHAR(20),     -- 'critical', 'warning', 'info'
    message TEXT,
    details JSONB,           -- Additional context (row count, examples, etc.)

    -- Metrics
    affected_rows INTEGER,
    total_rows INTEGER,
    percentage DECIMAL(5,2),

    -- Status
    status VARCHAR(20) DEFAULT 'open',  -- 'open', 'acknowledged', 'resolved'
    discovered_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(agent_id, schema_name, table_name, column_name, issue_type)
);

CREATE INDEX idx_dq_agent ON platform.data_quality_issues(agent_id);
CREATE INDEX idx_dq_severity ON platform.data_quality_issues(severity, status);
CREATE INDEX idx_dq_discovered ON platform.data_quality_issues(discovered_at);

COMMENT ON TABLE platform.data_quality_issues IS 'Stores data quality validation issues discovered during agent onboarding';
COMMENT ON COLUMN platform.data_quality_issues.issue_type IS 'Type: missing_primary_key, high_null_percentage, duplicate_rows, orphaned_records, etc.';
COMMENT ON COLUMN platform.data_quality_issues.severity IS 'Severity: critical (blocks), warning (review), info (fyi)';
