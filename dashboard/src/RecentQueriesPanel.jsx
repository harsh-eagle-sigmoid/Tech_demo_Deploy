import { useState, useEffect, Fragment } from 'react';
import { fetchHistory, fetchRunDetails } from './api';
import { ChevronDown, ChevronRight, CheckCircle, XCircle, Database } from 'lucide-react';

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
            setQueries(Array.isArray(data) ? data : []);
            setLoading(false);
        }).catch(err => {
            console.error("Failed to load history", err);
            setLoading(false);
        });
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

    if (!loading && queries.length === 0) return (
        <div className="panel" style={{ marginTop: '20px' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Database size={18} color="#4c9eff" />
                Recent Queries & SQL Analysis
            </h3>
            <p style={{ color: '#64748b', textAlign: 'center', padding: '20px' }}>No queries found.</p>
        </div>
    );

    return (
        <div className="panel" style={{ marginTop: '20px', overflow: 'hidden' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Database size={18} color="#4c9eff" />
                Recent Queries & SQL Analysis
            </h3>

            <table className="data-table" style={{ tableLayout: 'fixed', width: '100%' }}>
                <thead>
                    <tr>
                        <th style={{ width: '40px' }}></th>
                        <th>User Query</th>
                        <th style={{ width: '120px' }}>Correctness</th>
                        <th style={{ width: '100px' }}>Output Score</th>
                        <th style={{ width: '100px' }}>Confidence</th>
                        <th style={{ width: '150px' }}>Timestamp</th>
                    </tr>
                </thead>
                <tbody>
                    {queries.map(q => {
                        const isExpanded = expandedIds.has(q.query_id);
                        const detail = details[q.query_id];

                        return (
                            <Fragment key={q.query_id}>
                                <tr onClick={() => toggleExpand(q.query_id)} style={{ cursor: 'pointer', background: isExpanded ? '#1e293b' : 'transparent' }}>
                                    <td>
                                        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                                    </td>
                                    <td style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={q.prompt}>{q.prompt}</td>
                                    <td>
                                        <Badge status={q.correctness_verdict} />
                                    </td>
                                    <td style={{ fontWeight: 600, color: q.output_score !== null ? '#ff9f43' : '#64748b' }}>
                                        {q.output_score !== null && q.output_score !== undefined
                                            ? (q.output_score * 100).toFixed(0) + '%'
                                            : 'N/A'}
                                    </td>
                                    <td style={{ color: '#64748b' }}>
                                        {q.correctness_verdict === 'FAIL' ? '—' : `${Math.round((q.evaluation_confidence || 0) * 100)}%`}
                                    </td>
                                    <td style={{ fontSize: '0.85em', color: '#64748b' }}>
                                        {q.timestamp ? new Date(q.timestamp).toLocaleTimeString() : 'N/A'}
                                    </td>
                                </tr>
                                {isExpanded && (
                                    <tr>
                                        <td colSpan="6" style={{ padding: 0, background: '#0f172a' }}>
                                            <div className="detail-view fade-in" style={{ padding: '20px', borderLeft: '4px solid #4c9eff', overflow: 'hidden', maxWidth: '100%' }}>

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
                                                    {(detail?.evaluation?.verdict || q.correctness_verdict) !== 'FAIL' && (
                                                        <div className="detail-metric">
                                                            <div className="label">Confidence Score</div>
                                                            <div className="big-value" style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#fff' }}>
                                                                {detail ? Math.round((detail.evaluation?.confidence || 0) * 100) : Math.round((q.evaluation_confidence || 0) * 100)}%
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Score Breakdown - adapts to evaluation type */}
                                                {detail?.evaluation?.scores && Object.keys(detail.evaluation.scores).length > 0 && (
                                                    <div style={{ marginBottom: '20px' }}>
                                                        <div className="label" style={{ marginBottom: '8px', fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>
                                                            {detail.evaluation.scores.intent !== undefined ? 'HEURISTIC BREAKDOWN' : 'EVALUATION BREAKDOWN'}
                                                        </div>
                                                        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${detail.evaluation.scores.intent !== undefined ? 4 : (detail.evaluation.scores.result_validation !== undefined ? 4 : 3)}, 1fr)`, gap: '10px' }}>
                                                            {detail.evaluation.scores.intent !== undefined ? (
                                                                <>
                                                                    <ScoreCard label="Structural" score={detail.evaluation.scores.structural} />
                                                                    <ScoreCard label="Intent" score={detail.evaluation.scores.intent} />
                                                                    <ScoreCard label="Pattern" score={detail.evaluation.scores.pattern} />
                                                                    <ScoreCard label="Drift" score={detail.evaluation.scores.drift} isPenalty={true} />
                                                                </>
                                                            ) : (
                                                                <>
                                                                    <ScoreCard label="Structural" score={detail.evaluation.scores.structural} />
                                                                    <ScoreCard label="Semantic" score={detail.evaluation.scores.semantic} />
                                                                    <ScoreCard label="LLM Judge" score={detail.evaluation.scores.llm} />
                                                                    {detail.evaluation.scores.result_validation !== undefined && (
                                                                        <ScoreCard label="Output Match ⭐" score={detail.evaluation.scores.result_validation} isHighlight={true} />
                                                                    )}
                                                                </>
                                                            )}
                                                        </div>
                                                    </div>
                                                )}

                                                {/* Query Output Results */}
                                                {detail?.evaluation?.result_validation && (
                                                    <div className="sql-box" style={{ marginBottom: '20px' }}>
                                                        <div className="label" style={{ marginBottom: '8px', fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>
                                                            OUTPUT VALIDATION RESULTS
                                                        </div>
                                                        <div style={{
                                                            background: '#1e293b',
                                                            padding: '15px',
                                                            borderRadius: '8px',
                                                            border: '1px solid #334155'
                                                        }}>
                                                            {/* PATH B: GT comparison metrics */}
                                                            {detail.evaluation.result_validation.schema_match !== undefined && detail.evaluation.result_validation.validation_type !== 'llm_enhanced' ? (
                                                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '15px', marginBottom: '15px' }}>
                                                                    <div>
                                                                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '4px' }}>Schema Match</div>
                                                                        <div style={{ fontSize: '0.95rem', fontWeight: 600, color: detail.evaluation.result_validation.schema_match ? '#3ecf8e' : '#ff6b6b' }}>
                                                                            {detail.evaluation.result_validation.schema_match ? '✓ Match' : '✗ Mismatch'}
                                                                        </div>
                                                                    </div>
                                                                    <div>
                                                                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '4px' }}>Row Count Match</div>
                                                                        <div style={{ fontSize: '0.95rem', fontWeight: 600, color: detail.evaluation.result_validation.row_count_match ? '#3ecf8e' : '#ff6b6b' }}>
                                                                            {detail.evaluation.result_validation.row_count_match ? '✓ Match' : '✗ Mismatch'}
                                                                        </div>
                                                                    </div>
                                                                    <div>
                                                                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '4px' }}>Content Match</div>
                                                                        <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#ff9f43' }}>
                                                                            {(detail.evaluation.result_validation.content_match_rate * 100).toFixed(1)}%
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            ) : (
                                                                /* PATH A: LLM-based output scores */
                                                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '15px', marginBottom: '15px' }}>
                                                                    <div>
                                                                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '4px' }}>LLM Correctness</div>
                                                                        <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#3ecf8e' }}>
                                                                            {detail.evaluation.result_validation.llm_correctness != null
                                                                                ? (detail.evaluation.result_validation.llm_correctness * 100).toFixed(0) + '%'
                                                                                : 'N/A'}
                                                                        </div>
                                                                    </div>
                                                                    <div>
                                                                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '4px' }}>Completeness</div>
                                                                        <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#4c9eff' }}>
                                                                            {detail.evaluation.result_validation.llm_completeness != null
                                                                                ? (detail.evaluation.result_validation.llm_completeness * 100).toFixed(0) + '%'
                                                                                : 'N/A'}
                                                                        </div>
                                                                    </div>
                                                                    <div>
                                                                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '4px' }}>Quality</div>
                                                                        <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#ff9f43' }}>
                                                                            {detail.evaluation.result_validation.llm_quality != null
                                                                                ? (detail.evaluation.result_validation.llm_quality * 100).toFixed(0) + '%'
                                                                                : 'N/A'}
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            )}
                                                            {detail.evaluation.result_validation.error && (
                                                                <div style={{
                                                                    padding: '10px',
                                                                    background: 'rgba(255, 107, 107, 0.1)',
                                                                    borderRadius: '6px',
                                                                    color: '#ff6b6b',
                                                                    fontSize: '0.85rem',
                                                                    border: '1px solid rgba(255, 107, 107, 0.3)'
                                                                }}>
                                                                    ⚠ Error: {detail.evaluation.result_validation.error}
                                                                </div>
                                                            )}
                                                            {detail.evaluation.result_validation.generated_time_ms && (
                                                                <div style={{ marginTop: '10px', fontSize: '0.75rem', color: '#94a3b8' }}>
                                                                    Execution: {detail.evaluation.result_validation.generated_time_ms.toFixed(1)}ms
                                                                    {detail.evaluation.result_validation.gt_time_ms && ` | Ground Truth ${detail.evaluation.result_validation.gt_time_ms.toFixed(1)}ms`}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                )}

                                                {/* Query Output Display - Enhanced Format */}
                                                {detail?.evaluation?.result_validation?.details?.output_sample && (
                                                    <div style={{ marginTop: '20px', marginBottom: '15px' }}>
                                                        <div style={{
                                                            marginBottom: '12px',
                                                            padding: '10px 14px',
                                                            background: 'linear-gradient(to right, rgba(96, 165, 250, 0.15), transparent)',
                                                            borderLeft: '3px solid #60a5fa',
                                                            borderRadius: '4px'
                                                        }}>
                                                            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#60a5fa', letterSpacing: '0.5px' }}>
                                                                QUERY RESULT
                                                            </div>
                                                            <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '2px' }}>
                                                                Showing {detail.evaluation.result_validation.details.output_sample.rows.length} of {detail.evaluation.result_validation.details.gen_row_count} rows
                                                            </div>
                                                        </div>
                                                        <div style={{
                                                            background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
                                                            padding: '16px',
                                                            borderRadius: '10px',
                                                            border: '1px solid #334155',
                                                            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)',
                                                            overflowX: 'auto'
                                                        }}>
                                                            <table style={{
                                                                width: '100%',
                                                                borderCollapse: 'separate',
                                                                borderSpacing: 0,
                                                                fontSize: '0.9rem'
                                                            }}>
                                                                <thead>
                                                                    <tr>
                                                                        {detail.evaluation.result_validation.details.output_sample.columns.map((col, idx) => (
                                                                            <th key={idx} style={{
                                                                                padding: '12px 16px',
                                                                                textAlign: 'left',
                                                                                background: 'rgba(96, 165, 250, 0.15)',
                                                                                color: '#60a5fa',
                                                                                fontWeight: 700,
                                                                                fontSize: '0.8rem',
                                                                                textTransform: 'uppercase',
                                                                                letterSpacing: '0.5px',
                                                                                borderBottom: '2px solid #60a5fa',
                                                                                whiteSpace: 'nowrap',
                                                                                ...(idx === 0 && { borderTopLeftRadius: '6px' }),
                                                                                ...(idx === detail.evaluation.result_validation.details.output_sample.columns.length - 1 && { borderTopRightRadius: '6px' })
                                                                            }}>
                                                                                {col}
                                                                            </th>
                                                                        ))}
                                                                    </tr>
                                                                </thead>
                                                                <tbody>
                                                                    {detail.evaluation.result_validation.details.output_sample.rows.map((row, rowIdx) => (
                                                                        <tr key={rowIdx} style={{
                                                                            borderBottom: rowIdx < detail.evaluation.result_validation.details.output_sample.rows.length - 1 ? '1px solid #334155' : 'none',
                                                                            background: rowIdx % 2 === 0 ? 'rgba(15, 23, 42, 0.6)' : 'transparent',
                                                                            transition: 'background 0.2s ease'
                                                                        }}
                                                                        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(96, 165, 250, 0.08)'}
                                                                        onMouseLeave={(e) => e.currentTarget.style.background = rowIdx % 2 === 0 ? 'rgba(15, 23, 42, 0.6)' : 'transparent'}>
                                                                            {row.map((cell, cellIdx) => {
                                                                                const isNumeric = !isNaN(cell) && cell !== null && cell !== '';
                                                                                return (
                                                                                    <td key={cellIdx} style={{
                                                                                        padding: '12px 16px',
                                                                                        color: cell === null || cell === undefined ? '#94a3b8' : '#e2e8f0',
                                                                                        fontFamily: isNumeric ? 'monospace' : 'inherit',
                                                                                        fontSize: '0.9rem',
                                                                                        fontWeight: isNumeric ? 600 : 400,
                                                                                        textAlign: isNumeric ? 'right' : 'left',
                                                                                        whiteSpace: 'nowrap'
                                                                                    }}>
                                                                                        {cell !== null && cell !== undefined ? (
                                                                                            <span style={{ color: isNumeric ? '#34d399' : '#e2e8f0' }}>
                                                                                                {String(cell)}
                                                                                            </span>
                                                                                        ) : (
                                                                                            <span style={{ fontStyle: 'italic', opacity: 0.6 }}>NULL</span>
                                                                                        )}
                                                                                    </td>
                                                                                );
                                                                            })}
                                                                        </tr>
                                                                    ))}
                                                                </tbody>
                                                            </table>
                                                            {detail.evaluation.result_validation.details.gen_row_count > detail.evaluation.result_validation.details.output_sample.rows.length && (
                                                                <div style={{
                                                                    marginTop: '14px',
                                                                    padding: '10px 14px',
                                                                    background: 'linear-gradient(to right, rgba(96, 165, 250, 0.12), rgba(96, 165, 250, 0.05))',
                                                                    borderRadius: '6px',
                                                                    fontSize: '0.8rem',
                                                                    color: '#60a5fa',
                                                                    textAlign: 'center',
                                                                    fontWeight: 500,
                                                                    border: '1px dashed rgba(96, 165, 250, 0.3)'
                                                                }}>
                                                                    + {detail.evaluation.result_validation.details.gen_row_count - detail.evaluation.result_validation.details.output_sample.rows.length} more rows not shown
                                                                </div>
                                                            )}
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
                                                        whiteSpace: 'pre-wrap',
                                                        wordBreak: 'break-word',
                                                        fontFamily: 'monospace',
                                                        fontSize: '0.9rem',
                                                        color: '#e2e8f0',
                                                        border: '1px solid #334155',
                                                        maxWidth: '100%'
                                                    }}>
                                                        {detail ? (detail.generated_sql || "-- No SQL Generated") : "Loading Details..."}
                                                    </pre>
                                                </div>

                                            </div>
                                        </td>
                                    </tr>
                                )}
                            </Fragment>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

const ScoreCard = ({ label, score, isPenalty = false, isHighlight = false }) => {
    const safeScore = score ?? 0;

    let color = '#fff';
    if (isPenalty) {
        if (safeScore < 0.65) color = '#3ecf8e';
        else if (safeScore < 0.85) color = '#f59f00';
        else color = '#ff6b6b';
    } else {
        if (safeScore > 0.8) color = '#3ecf8e';
        else if (safeScore > 0.5) color = '#f59f00';
        else color = '#ff6b6b';
    }

    return (
        <div style={{
            background: isHighlight ? 'rgba(255, 159, 67, 0.1)' : '#0f172a',
            padding: '12px',
            borderRadius: '8px',
            border: isHighlight ? '1px solid rgba(255, 159, 67, 0.4)' : '1px solid #334155'
        }}>
            <div style={{
                fontSize: '0.75rem',
                color: isHighlight ? '#ff9f43' : '#94a3b8',
                marginBottom: '4px',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                fontWeight: isHighlight ? 600 : 400
            }}>
                {label}
            </div>
            <div style={{ fontSize: '1.1rem', fontWeight: 'bold', color: isHighlight ? '#ff9f43' : color }}>
                {safeScore.toFixed(4)}
            </div>
        </div>
    );
};

const Badge = ({ status }) => {
    let color = 'medium';
    if (status === 'PASS') color = 'low';
    if (status === 'FAIL') color = 'critical';

    return <span className={`badge ${color}`}>{status}</span>;
};
