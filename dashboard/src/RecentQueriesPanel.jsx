import { useState, useEffect } from 'react';
import { fetchHistory, fetchRunDetails } from './api';
import { ChevronDown, ChevronRight, CheckCircle, XCircle, AlertTriangle, Database } from 'lucide-react';

export default function RecentQueriesPanel({ agentId, isActive = true }) {
    const [queries, setQueries] = useState([]);
    const [expandedIds, setExpandedIds] = useState(new Set());
    const [details, setDetails] = useState({}); // Cache for details: { queryId: detailObj }
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!isActive) return;
        loadHistory();
        const interval = setInterval(loadHistory, 5000);
        return () => clearInterval(interval);
    }, [agentId, isActive]);

    const loadHistory = () => {
        fetchHistory(20, agentId).then(data => {
            setQueries(data);
            setLoading(false);
        }).catch(err => console.error("Failed to load history", err));
    };

    const toggleExpand = async (queryId) => {
        const newExpanded = new Set(expandedIds);
        if (newExpanded.has(queryId)) {
            newExpanded.delete(queryId);
        } else {
            newExpanded.add(queryId);
            // Fetch details if not cached
            if (!details[queryId]) {
                try {
                    const detailData = await fetchRunDetails(queryId);
                    setDetails(prev => ({ ...prev, [queryId]: detailData }));
                } catch (err) {
                    console.error("Failed to fetch details", err);
                }
            }
        }
        setExpandedIds(newExpanded);
    };

    if (loading && queries.length === 0) return <div className="panel">Loading recent queries...</div>;

    return (
        <div className="panel" style={{ marginTop: '20px' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Database size={18} color="#4c9eff" />
                Recent Queries & SQL Analysis
            </h3>

            <table className="data-table">
                <thead>
                    <tr>
                        <th style={{ width: '40px' }}></th>
                        <th>User Query</th>
                        <th style={{ width: '120px' }}>Correctness</th>
                        <th style={{ width: '100px' }}>Confidence</th>
                        <th style={{ width: '150px' }}>Timestamp</th>
                    </tr>
                </thead>
                <tbody>
                    {queries.map(q => {
                        const isExpanded = expandedIds.has(q.query_id);
                        const detail = details[q.query_id];

                        return (
                            <>
                                <tr key={q.query_id} onClick={() => toggleExpand(q.query_id)} style={{ cursor: 'pointer', background: isExpanded ? '#1e293b' : 'transparent' }}>
                                    <td>
                                        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                                    </td>
                                    <td style={{ fontWeight: 500 }}>{q.prompt}</td>
                                    <td>
                                        <Badge status={q.correctness_verdict} />
                                    </td>
                                    <td>{Math.round(q.evaluation_confidence * 100)}%</td>
                                    <td style={{ fontSize: '0.85em', color: '#64748b' }}>
                                        {new Date(q.timestamp).toLocaleTimeString()}
                                    </td>
                                </tr>
                                {isExpanded && (
                                    <tr key={`${q.query_id}-detail`}>
                                        <td colSpan="5" style={{ padding: 0, background: '#0f172a' }}>
                                            <div className="detail-view fade-in" style={{ padding: '20px', borderLeft: '4px solid #4c9eff' }}>

                                                {/* Detail Grid */}
                                                <div style={{ display: 'flex', gap: '40px', marginBottom: '20px' }}>
                                                    <div className="detail-metric">
                                                        <div className="label">Evaluation Verdict</div>
                                                        <div className="big-value" style={{
                                                            color: (detail?.evaluation?.verdict === 'PASS' || q.correctness_verdict === 'PASS') ? '#3ecf8e' : '#ff6b6b',
                                                            display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.2rem', fontWeight: 'bold'
                                                        }}>
                                                            {(detail?.evaluation?.verdict === 'PASS' || q.correctness_verdict === 'PASS') ? <CheckCircle /> : <XCircle />}
                                                            {detail?.evaluation?.verdict || q.correctness_verdict}
                                                        </div>
                                                    </div>
                                                    <div className="detail-metric">
                                                        <div className="label">Confidence Score</div>
                                                        <div className="big-value" style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#fff' }}>
                                                            {detail ? Math.round((detail.evaluation?.confidence || 0) * 100) : Math.round(q.evaluation_confidence * 100)}%
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Heuristic Breakdown */}
                                                {detail?.evaluation?.scores && (
                                                    <div style={{ marginBottom: '20px' }}>
                                                        <div className="label" style={{ marginBottom: '8px', fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>HEURISTIC BREAKDOWN</div>
                                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
                                                            <ScoreCard label="Structural" score={detail.evaluation.scores.structural} />
                                                            <ScoreCard label="Intent" score={detail.evaluation.scores.intent} />
                                                            <ScoreCard label="Pattern" score={detail.evaluation.scores.pattern} />
                                                            <ScoreCard label="Drift" score={detail.evaluation.scores.drift} isPenalty={true} />
                                                        </div>
                                                    </div>
                                                )}

                                                <div className="sql-box">
                                                    <div className="label" style={{ marginBottom: '8px', fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>GENERATED SQL</div>
                                                    <pre style={{
                                                        background: '#1e293b',
                                                        padding: '15px',
                                                        borderRadius: '8px',
                                                        overflowX: 'auto',
                                                        fontFamily: 'monospace',
                                                        fontSize: '0.9rem',
                                                        color: '#e2e8f0',
                                                        border: '1px solid #334155'
                                                    }}>
                                                        {detail ? (detail.generated_sql || "-- No SQL Generated") : "Loading Details..."}
                                                    </pre>
                                                </div>

                                            </div>
                                        </td>
                                    </tr>
                                )}
                            </>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

const ScoreCard = ({ label, score, isPenalty = false }) => {
    // Determine color
    let color = '#fff'; // default

    if (isPenalty) {
        // For Penalty (like Drift): Low (0.0) is Good (Green), High (1.0) is Bad (Red)
        if (score < 0.65) color = '#3ecf8e';       // Good
        else if (score < 0.85) color = '#f59f00'; // Warning
        else color = '#ff6b6b';                   // Critical
    } else {
        // For Score (like Structural): High (1.0) is Good (Green), Low (0.0) is Bad (Red)
        if (score > 0.8) color = '#3ecf8e';        // Good
        else if (score > 0.5) color = '#f59f00'; // Warning
        else color = '#ff6b6b';                   // Critical
    }

    return (
        <div style={{ background: '#0f172a', padding: '12px', borderRadius: '8px', border: '1px solid #334155' }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {label}
            </div>
            <div style={{ fontSize: '1.1rem', fontWeight: 'bold', color: color }}>
                {isPenalty ? score.toFixed(2) : (score * 100).toFixed(0) + '%'}
            </div>
        </div>
    );
};

const Badge = ({ status }) => {
    let color = 'medium'; // gray/blue
    if (status === 'PASS') color = 'low'; // green
    if (status === 'FAIL') color = 'critical'; // red

    return <span className={`badge ${color}`}>{status}</span>;
};
