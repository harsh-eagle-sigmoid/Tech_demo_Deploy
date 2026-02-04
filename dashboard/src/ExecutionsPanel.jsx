import { useState, useEffect } from 'react';
import { fetchHistory } from './api';

export default function ExecutionsPanel() {
    const [runs, setRuns] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadHistory();
        const interval = setInterval(loadHistory, 5000); // Poll every 5s
        return () => clearInterval(interval);
    }, []);

    const loadHistory = () => {
        fetchHistory()
            .then(data => {
                setRuns(data);
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to load history", err);
                setLoading(false);
            });
    };

    return (
        <div className="panel">
            <div className="panel-header">
                <h2>Execution Runs</h2>
                <span className="refresh-info">Auto-refreshing every 5s</span>
            </div>

            <div className="table-wrapper" style={{ overflowX: 'auto' }}>
                <table className="runs-table" style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1rem' }}>
                    <thead>
                        <tr style={{ textAlign: 'left', borderBottom: '2px solid #eee' }}>
                            <th style={{ padding: '10px' }}>Prompt</th>
                            <th style={{ padding: '10px' }}>Correctness Verdict</th>
                            <th style={{ padding: '10px' }}>Confidence</th>
                            <th style={{ padding: '10px' }}>Error Bucket</th>
                            <th style={{ padding: '10px' }}>Dataset</th>
                            <th style={{ padding: '10px' }}>Timestamp</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading && runs.length === 0 ? (
                            <tr><td colSpan="6" style={{ padding: '20px', textAlign: 'center' }}>Loading...</td></tr>
                        ) : runs.map((run) => (
                            <tr key={run.query_id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                                <td style={{ padding: '10px', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={run.prompt}>
                                    {run.prompt}
                                </td>
                                <td style={{ padding: '10px' }}>
                                    <span style={{
                                        padding: '4px 8px',
                                        borderRadius: '4px',
                                        fontSize: '0.85em',
                                        backgroundColor: run.correctness_verdict === 'PASS' ? '#dcfce7' : (run.correctness_verdict === 'FAIL' ? '#fee2e2' : '#f3f4f6'),
                                        color: run.correctness_verdict === 'PASS' ? '#166534' : (run.correctness_verdict === 'FAIL' ? '#991b1b' : '#374151')
                                    }}>
                                        {run.correctness_verdict}
                                    </span>
                                </td>
                                <td style={{ padding: '10px' }}>
                                    {(run.evaluation_confidence * 100).toFixed(1)}%
                                </td>
                                <td style={{ padding: '10px' }}>
                                    {run.error_bucket !== 'None' ? (
                                        <span style={{ color: '#dc2626', fontWeight: 500 }}>{run.error_bucket}</span>
                                    ) : (
                                        <span style={{ color: '#9ca3af' }}>-</span>
                                    )}
                                </td>
                                <td style={{ padding: '10px' }}>
                                    <span style={{
                                        fontWeight: 'bold',
                                        color: run.dataset.toLowerCase() === 'spend' ? '#2563eb' : '#d97706'
                                    }}>
                                        {run.dataset.toUpperCase()}
                                    </span>
                                </td>
                                <td style={{ padding: '10px', color: '#6b7280', fontSize: '0.9em' }}>
                                    {new Date(run.timestamp).toLocaleString()}
                                </td>
                            </tr>
                        ))}
                        {!loading && runs.length === 0 && (
                            <tr><td colSpan="6" style={{ padding: '20px', textAlign: 'center', color: '#888' }}>No execution history found yet.</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
