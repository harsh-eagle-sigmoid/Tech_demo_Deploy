import { useState } from 'react';
import { sendQuery } from './api';

export default function QueryPanel() {
  const [agentType, setAgentType] = useState('spend');
  const [query,     setQuery]     = useState('');
  const [result,    setResult]    = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await sendQuery(query.trim(), agentType);
      if (res.status === 'error') {
        setError(res.error);
      } else {
        setResult(res);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Derive column headers from first result row
  const columns = result?.results?.length ? Object.keys(result.results[0]) : [];

  return (
    <>
      <div className="cards-row">
        <div className="card">
          <div className="label">Spend Agent</div>
          <div className="value blue" style={{ fontSize: '1rem' }}>localhost:8001</div>
        </div>
        <div className="card">
          <div className="label">Demand Agent</div>
          <div className="value blue" style={{ fontSize: '1rem' }}>localhost:8002</div>
        </div>
        <div className="card">
          <div className="label">Gateway</div>
          <div className="value green" style={{ fontSize: '1rem' }}>localhost:8000</div>
        </div>
      </div>

      <div className="panel">
        <h3>Send a Query</h3>
        <form className="query-form" onSubmit={handleSubmit}>
          <select value={agentType} onChange={e => setAgentType(e.target.value)}>
            <option value="spend">Spend Agent</option>
            <option value="demand">Demand Agent</option>
          </select>
          <input
            type="text"
            placeholder="e.g. What is total revenue by category?"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          <button type="submit" className="btn-primary" disabled={loading || !query.trim()}>
            {loading ? 'Sending…' : 'Send'}
          </button>
        </form>

        {/* Quick-pick examples */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
          {agentType === 'spend'
            ? ['What is total revenue?', 'Show orders with high priority', 'How many products are in Technology?']
            : ['Which products have low stock?', 'Show me average price by product type', 'Which products are unavailable?']
          }.map(ex => (
            <button key={ex} onClick={() => setQuery(ex)}
              style={{ background: '#1a2232', border: '1px solid #2a3548', borderRadius: 5, color: '#7a8fa3', padding: '4px 10px', fontSize: '0.78rem', cursor: 'pointer' }}>
              {ex}
            </button>
          ))}
        </div>

        {loading && <p className="loading">Querying {agentType} agent…</p>}
        {error  && <p className="error-msg">{error}</p>}

        {result && (
          <div className="result-box">
            <div className="sql-label">Generated SQL</div>
            <pre>{result.sql}</pre>
            <div className="sql-label">Results ({result.results.length} rows)</div>
            <div className="result-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>{columns.map(c => <th key={c}>{c}</th>)}</tr>
                </thead>
                <tbody>
                  {result.results.map((row, i) => (
                    <tr key={i}>{columns.map(c => <td key={c}>{String(row[c] ?? '')}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
