import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './ExecutionTrace.css';

export default function ExecutionTrace({ runId, onClose }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!runId) return;

        setLoading(true);
        // Determine API Base URL
        const API_BASE = import.meta.env.VITE_API_URL || '';

        axios.get(`${API_BASE}/api/v1/monitor/runs/${runId}`)
            .then(res => {
                setData(res.data);
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to load run:", err);
                setError("Run not found or API error.");
                setLoading(false);
            });
    }, [runId]);

    if (!runId) return null;
    if (loading) return <div className="trace-loading">Loading Trace {runId}...</div>;
    if (error) return <div className="trace-error">{error}</div>;

    const isCorrect = data.evaluation.verdict === 'PASS' || data.evaluation.verdict === 'Correct';
    const confidence = Math.round(data.evaluation.confidence * 100);

    return (
        <div className="trace-container" style={{ minHeight: 'auto', borderTop: '2px solid #30363d', marginTop: '20px' }}>
            {/* Header Controls */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '10px' }}>
                <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', fontSize: '20px' }}>&times; Close</button>
            </div>

            {/* Header: Verdict */}
            <div className={`verdict-banner ${isCorrect ? 'verdict-pass' : 'verdict-fail'}`}>
                <div className="verdict-icon">{isCorrect ? '✓' : '⚠'}</div>
                <div className="verdict-info">
                    <div className="verdict-label">CORRECTNESS VERDICT</div>
                    <div className="verdict-value">{isCorrect ? 'Correct' : 'Incorrect'}</div>
                </div>
                <div className="verdict-confidence">
                    <div className="confidence-label">EVALUATION CONFIDENCE</div>
                    <div className="confidence-value">{confidence}%</div>
                </div>
            </div>

            <div className="trace-header">
                <span className="trace-id">Trace-{data.query_id.slice(-4)} • {data.timestamp?.split('T')[0]} • {data.status}</span>
            </div>

            {/* Heuristic Breakdown */}
            {data.evaluation?.scores && data.evaluation.scores.structural !== undefined && (
                <div style={{ marginBottom: '20px', padding: '0 20px', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
                    <TraceScoreCard label="Structural" score={data.evaluation.scores.structural} />
                    <TraceScoreCard label="Intent" score={data.evaluation.scores.intent} />
                    <TraceScoreCard label="Pattern" score={data.evaluation.scores.pattern} />
                    <TraceScoreCard label="Drift" score={data.evaluation.scores.drift} isPenalty={true} />
                </div>
            )}

            <div className="trace-content">
                <h3>Execution Trace</h3>
                <p className="subtitle">What the agent did</p>

                <div className="row">
                    <div className="col">
                        <label>AGENT TYPE</label>
                        <div className="value-box">{data.agent_type.toUpperCase().replace('_', ' ')} GPT</div>
                    </div>
                    <div className="col">
                        <label>DRIFT STATUS</label>
                        <div className="value-box" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{
                                color: data.drift?.status === 'high' ? '#ff6b6b' : '#3fb950',
                                fontWeight: 'bold',
                                textTransform: 'uppercase'
                            }}>
                                {data.drift?.status || 'UNKNOWN'}
                            </span>
                            <span style={{ fontSize: '0.8em', opacity: 0.7 }}>
                                (Score: {Number(data.drift?.score || 0).toFixed(2)})
                            </span>
                        </div>
                    </div>
                </div>

                <div className="section">
                    <label>USER PROMPT</label>
                    <div className="prompt-box">{data.user_prompt}</div>
                </div>


                <div className="section">
                    <label>GENERATED SQL</label>
                    <div className="code-box sql">
                        {data.generated_sql || "-- No SQL generated"}
                    </div>
                </div>
            </div>
        </div>
    );
}

const TraceScoreCard = ({ label, score, isPenalty = false }) => {
    if (score === undefined || score === null) return null;

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
        <div style={{ background: '#161b22', padding: '10px', borderRadius: '6px', border: '1px solid #30363d', textAlign: 'center' }}>
            <div style={{ fontSize: '0.7em', color: '#8b949e', marginBottom: '4px', textTransform: 'uppercase' }}>
                {label}
            </div>
            <div style={{ fontSize: '1.2em', fontWeight: 'bold', color: color }}>
                {isPenalty ? score.toFixed(2) : (score * 100).toFixed(0) + '%'}
            </div>
        </div>
    );
};
