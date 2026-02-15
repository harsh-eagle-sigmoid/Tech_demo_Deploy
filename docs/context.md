# Unilever Procurement GPT POC — Project Context

> Last Updated: 2026-02-03

---

## Project Overview

A Text-to-SQL AI system for Unilever procurement analytics with:
- Two independent AI agents (Spend & Demand)
- 6-step evaluation pipeline
- Drift detection & error classification
- Automated monitoring on every query
- React dashboard for visualization

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER / DASHBOARD                                │
│                        (React - port 3000)                              │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (port 8000)                            │
│                                                                         │
│  POST /api/v1/query  ──────────────────────────────────────────────┐   │
│       │                                                             │   │
│       ├─► 1. Call Agent (8001 or 8002)                             │   │
│       ├─► 2. Auto Drift Detection → monitoring.drift_monitoring    │   │
│       ├─► 3. Auto Error Classification → monitoring.errors         │   │
│       └─► 4. Auto Evaluation (if GT exists) → monitoring.evaluations   │
│                                                                         │
│  Other endpoints: /metrics, /drift, /errors, /evaluate, /baseline      │
└─────────────────────────────────────────────────────────────────────────┘
                          │                    │
                          ▼                    ▼
┌─────────────────────────────┐    ┌─────────────────────────────┐
│      SPEND AGENT            │    │      DEMAND AGENT           │
│      (port 8001)            │    │      (port 8002)            │
│                             │    │                             │
│  - Azure OpenAI GPT-4o      │    │  - Azure OpenAI GPT-4o      │
│  - spend_data schema        │    │  - demand_data schema       │
│  - Few-shot examples        │    │  - Few-shot examples        │
└─────────────────────────────┘    └─────────────────────────────┘
                          │                    │
                          ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL + pgvector                                │
│                                                                         │
│  Schemas:                                                               │
│  ├── spend_data (orders, products, customers)                          │
│  ├── demand_data (products, sales, suppliers, supply_chain)            │
│  └── monitoring (evaluations, drift_monitoring, errors, baseline)      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
/home/lenovo/Desktop/
├── spend_agent/                    # Independent Spend Agent
│   ├── __init__.py
│   ├── agent.py                    # SpendAgent class (Azure OpenAI)
│   └── run.py                      # FastAPI server (port 8001)
│
├── demand_agent/                   # Independent Demand Agent
│   ├── __init__.py
│   ├── agent.py                    # DemandAgent class (Azure OpenAI)
│   └── run.py                      # FastAPI server (port 8002)
│
└── New_tech_demo/                  # Main Framework
    ├── .env                        # Azure OpenAI + DB credentials
    ├── context.md                  # THIS FILE
    │
    ├── api/
    │   └── main.py                 # API Gateway (port 8000) - AUTOMATED PIPELINE
    │
    ├── config/
    │   └── settings.py             # Pydantic settings
    │
    ├── database/
    │   ├── init_db.py              # Create schemas & tables
    │   ├── load_data.py            # Load CSV data
    │   ├── connection.py           # DB connection helper
    │   └── schemas.py              # SQLAlchemy models
    │
    ├── data/
    │   ├── ground_truth/
    │   │   ├── all_queries.json    # 946 ground truth queries
    │   │   ├── train.json          # 567 queries (60%)
    │   │   ├── test.json           # 283 queries (30%)
    │   │   └── validation.json     # 96 queries (10%)
    │   ├── agent_outputs.json      # Agent-generated outputs
    │   ├── ground_truth_generator.py
    │   └── ground_truth_generator_1000.py
    │
    ├── evaluation/
    │   ├── validators.py           # Step 2: Structural validation
    │   ├── semantic_checker.py     # Step 3: Semantic comparison
    │   ├── llm_judge.py            # Step 4: LLM-as-Judge (Azure)
    │   ├── evaluator.py            # Main orchestrator (6 steps)
    │   └── test_evaluator.py       # Batch evaluation runner
    │
    ├── monitoring/
    │   ├── drift_detector.py       # Embedding-based drift detection
    │   ├── error_classifier.py     # Rule-based error classification
    │   └── monitor.py              # Batch monitoring runner
    │
    ├── agents/
    │   ├── run_agents.py           # HTTP runner (calls 8001/8002)
    │   ├── base_agent.py           # (legacy)
    │   ├── spend_agent.py          # (legacy)
    │   ├── demand_agent.py         # (legacy)
    │   └── llm_client.py           # Azure OpenAI client
    │
    ├── dashboard/                  # React Dashboard
    │   ├── package.json
    │   ├── vite.config.js          # Proxy to port 8000
    │   └── src/
    │       ├── App.jsx             # Main app with tabs
    │       ├── App.css             # Dark theme styles
    │       ├── api.js              # API calls
    │       ├── MetricsPanel.jsx    # Evaluation metrics
    │       ├── DriftPanel.jsx      # Drift monitoring
    │       ├── ErrorsPanel.jsx     # Error analytics
    │       └── QueryPanel.jsx      # Query interface
    │
    ├── logs/                       # Log files
    └── venv/                       # Python virtual environment
```

---

## Database Schema

### spend_data
- `orders`: order_id, order_date, ship_date, ship_mode, customer_id, product_id, sales, quantity, discount, profit, shipping_cost, order_priority
- `products`: product_id, category, sub_category, product_name
- `customers`: customer_id, customer_name, segment, city, state, country, market, region

### demand_data
- `products`: sku, product_type, price, availability, stock_levels, customer_demographics, created_at
- `sales`: sales_id, sku, products_sold, revenue_generated, order_quantities, created_at
- `suppliers`: supplier_id, supplier_name, location, lead_time, shipping_carrier, transportation_mode, route
- `supply_chain`: id, sku, supplier_id, lead_time, shipping_time, shipping_cost, production_volume, manufacturing_lead_time, manufacturing_cost, inspection_result, defect_rate, total_cost

### monitoring
- `evaluations`: query_id, query_text, agent_type, complexity, generated_sql, ground_truth_sql, structural_score, semantic_score, llm_score, final_score, result, confidence, reasoning, evaluation_data (JSONB)
- `drift_monitoring`: query_id, query_embedding (vector 384), drift_score, drift_classification, similarity_to_baseline, is_anomaly
- `errors`: query_id, error_category, error_message, severity, suggested_fix, first_seen, last_seen
- `baseline`: agent_type, centroid_embedding (vector 384), num_queries, version

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Gateway + agent health status |
| POST | `/api/v1/query` | **AUTOMATED**: Agent + Drift + Errors + Evaluation |
| POST | `/api/v1/evaluate` | Manual evaluation |
| GET | `/api/v1/metrics` | Evaluation accuracy metrics |
| GET | `/api/v1/drift` | Drift distribution & anomalies |
| GET | `/api/v1/errors` | Error summary by category |
| GET | `/api/v1/errors/{category}` | Detailed errors for category |
| POST | `/api/v1/baseline/update` | Rebuild drift baseline |

---

## Evaluation Pipeline (6 Steps)

```
1. PREPROCESSING     → Clean SQL, remove markdown
2. STRUCTURAL (30%)  → Syntax check (EXPLAIN), schema validation
3. SEMANTIC (30%)    → Component comparison (SELECT, FROM, WHERE, etc.)
4. LLM JUDGE (40%)   → Azure GPT-4o evaluates equivalence
5. SCORING           → Weighted sum, threshold 0.7 for PASS
6. STORE             → Save to monitoring.evaluations
```

---

## Drift Detection

- **Model**: sentence-transformers/all-MiniLM-L6-v2 (384-dim embeddings)
- **Method**: Cosine similarity to baseline centroid
- **Levels**:
  - Normal: similarity >= 0.7
  - Medium: 0.5 <= similarity < 0.7
  - High: similarity < 0.5 (anomaly)

---

## Error Categories

| Category | Severity | Pattern |
|----------|----------|---------|
| SQL_GENERATION | high | syntax error, invalid column |
| CONTEXT_RETRIEVAL | high | no relevant context |
| DATA_ERROR | medium | null values, type mismatch |
| INTEGRATION | critical | connection refused, timeout |
| AGENT_LOGIC | medium | unexpected behavior |

---

## Commands

### Start All Services

```bash
# Terminal 1 - Spend Agent
cd /home/lenovo/Desktop
/home/lenovo/Desktop/New_tech_demo/venv/bin/python -m spend_agent.run

# Terminal 2 - Demand Agent
cd /home/lenovo/Desktop
/home/lenovo/Desktop/New_tech_demo/venv/bin/python -m demand_agent.run

# Terminal 3 - API Gateway
cd /home/lenovo/Desktop/New_tech_demo
venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 4 - React Dashboard
cd /home/lenovo/Desktop/New_tech_demo/dashboard
npm run dev
```

### Run in Background

```bash
# All services in background
cd /home/lenovo/Desktop && /home/lenovo/Desktop/New_tech_demo/venv/bin/python -m spend_agent.run > /home/lenovo/Desktop/New_tech_demo/logs/spend_agent.log 2>&1 &

cd /home/lenovo/Desktop && /home/lenovo/Desktop/New_tech_demo/venv/bin/python -m demand_agent.run > /home/lenovo/Desktop/New_tech_demo/logs/demand_agent.log 2>&1 &

/home/lenovo/Desktop/New_tech_demo/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 > /home/lenovo/Desktop/New_tech_demo/logs/api.log 2>&1 &

cd /home/lenovo/Desktop/New_tech_demo/dashboard && npm run dev &
```

### Database Operations

```bash
cd /home/lenovo/Desktop/New_tech_demo
venv/bin/python -m database.init_db    # Create tables
venv/bin/python -m database.load_data  # Load data
```

### Ground Truth & Evaluation

```bash
cd /home/lenovo/Desktop/New_tech_demo
venv/bin/python data/ground_truth_generator_1000.py  # Generate queries
venv/bin/python -m agents.run_agents                 # Collect outputs
venv/bin/python -m evaluation.test_evaluator         # Run evaluation
venv/bin/python -m monitoring.monitor                # Run monitoring
```

### Check Processes

```bash
ps aux | grep -E "spend_agent|demand_agent|uvicorn|vite" | grep -v grep
lsof -i :8000 -i :8001 -i :8002 -i :3000
```

### Kill Services

```bash
kill $(lsof -t -i:8000)  # API
kill $(lsof -t -i:8001)  # Spend Agent
kill $(lsof -t -i:8002)  # Demand Agent
kill $(lsof -t -i:3000)  # Dashboard
```

---

## URLs

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API Gateway | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Spend Agent | http://localhost:8001 |
| Demand Agent | http://localhost:8002 |

---

## Environment Variables (.env)

```
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com/
AZURE_OPENAI_API_KEY=xxx
AZURE_OPENAI_DEPLOYMENT=gpt-4o-harshal
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=unilever_poc
DB_USER=postgres
DB_PASSWORD=postgres

# Azure AD Authentication (Optional)
AZURE_AD_TENANT_ID=your-tenant-id
AZURE_AD_CLIENT_ID=your-client-id
AZURE_AD_CLIENT_SECRET=your-client-secret
AZURE_AD_AUDIENCE=api://your-client-id
AUTH_ENABLED=false
```

---

## Authentication (Azure AD)

### Overview
The system supports OAuth2/JWT authentication via Azure Active Directory. When enabled, all API endpoints require a valid Bearer token.

### Setup Steps

1. **Create App Registration in Azure Portal**
   - Go to Azure Portal → Azure Active Directory → App Registrations
   - Click "New registration"
   - Name: `Unilever-Procurement-GPT`
   - Supported account types: Single tenant (or as needed)
   - Redirect URI: `http://localhost:3000` (Web)

2. **Configure App Registration**
   - Note the Application (client) ID and Directory (tenant) ID
   - Go to "Certificates & secrets" → New client secret
   - Go to "Expose an API" → Add a scope (e.g., `access`)
   - Go to "API permissions" → Add permissions as needed

3. **Update .env file**
   ```
   AZURE_AD_TENANT_ID=<your-tenant-id>
   AZURE_AD_CLIENT_ID=<your-client-id>
   AZURE_AD_CLIENT_SECRET=<your-client-secret>
   AZURE_AD_AUDIENCE=api://<your-client-id>
   AUTH_ENABLED=true
   ```

4. **Restart API Gateway**
   - The API will now require authentication
   - Dashboard will show "Sign In with Azure AD" button

### Auth Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/auth/config` | Get auth configuration (public) |
| GET | `/api/v1/auth/me` | Get current user info (requires auth) |

### Files

```
auth/
├── __init__.py
└── azure_auth.py        # JWT validation, user extraction

dashboard/src/
├── authConfig.js        # MSAL configuration
└── AuthProvider.jsx     # React auth context
```

---

## Current Status

### Completed ✅
- [x] PostgreSQL + pgvector setup
- [x] Data loading (spend_data, demand_data)
- [x] Spend Agent (independent, port 8001) - 100% accuracy
- [x] Demand Agent (independent, port 8002) - 60% accuracy
- [x] Ground Truth (946 queries)
- [x] Evaluation Framework (6-step pipeline)
- [x] Monitoring Framework (drift + errors)
- [x] REST API Gateway (port 8000)
- [x] **AUTOMATED PIPELINE** - drift/error/eval on every query
- [x] React Dashboard (port 3000)
- [x] **Azure AD Authentication** - OAuth2/JWT (optional, AUTH_ENABLED=false by default)

### Pending / Partial
- [ ] Full 946 query evaluation (only 30 evaluated so far)
- [ ] Improve Demand Agent accuracy (60% → target 90%+)
- [ ] Generate full 2500 ground truth (reduced to 946 due to token budget)
- [ ] Dockerize for production
- [ ] Alerting (Slack/email on anomalies)

---

## Key Metrics (as of last run)

| Metric | Value |
|--------|-------|
| Total Evaluations | 30 |
| Overall Accuracy | 73.3% |
| Spend Agent Accuracy | 100% (10/10) |
| Demand Agent Accuracy | 60% (12/20) |
| Ground Truth Queries | 946 |
| Drift Anomalies Detected | 11 |

---

## Notes

1. **Agents are independent** - They run on Desktop, not inside the framework
2. **Evaluation requires Ground Truth** - New queries skip evaluation (no GT match)
3. **Drift baselines** - Must be rebuilt if ground truth changes
4. **LLM Judge uses Azure tokens** - Each evaluation = ~300 tokens
5. **Embedding model is local** - sentence-transformers runs on CPU, no tokens

---

## Troubleshooting

### API returns empty response
- Check if agents are running: `curl http://localhost:8001/health`
- Check API logs: `tail -f logs/api.log`

### Drift shows "unknown"
- Baselines may not exist: run `/api/v1/baseline/update`
- Or run `python -m monitoring.monitor` to build baselines

### Evaluation skipped
- Query doesn't match ground truth exactly (case-insensitive match)
- Check `data/ground_truth/all_queries.json` for available queries

### Dashboard not loading
- Check if Vite is running: `lsof -i :3000`
- Restart: `cd dashboard && npm run dev`
