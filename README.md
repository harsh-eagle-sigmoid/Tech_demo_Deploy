# Unilever Procurement GPT POC

AI-driven Evaluation and Monitoring Framework for Procurement Agents

## Project Overview

This POC system evaluates and monitors AI agents (Spend Agent and Demand Agent) that handle procurement queries using Text-to-SQL approach.

**Key Features:**
- Text-to-SQL AI Agents (Spend & Demand)
- Automated Evaluation Framework (≥90% accuracy)
- Drift Detection System
- Error Classification (5 categories)
- Real-time Monitoring Dashboard
- REST API

## Project Structure

```
unilever-procurement-poc/
├── agents/           # AI agents (Spend & Demand)
├── evaluation/       # Evaluation framework
├── monitoring/       # Drift detection & error classification
├── api/              # FastAPI REST API
├── database/         # Database models & connections
├── dashboard/        # Streamlit dashboard
├── data/             # Datasets & ground truth
├── tests/            # Unit & integration tests
├── docs/             # Documentation
└── config/           # Configuration files
```

## Tech Stack

- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Database:** PostgreSQL 15+ with pgvector
- **LLM:** Ollama + Llama 3.1 8B (free, local)
- **Embeddings:** Sentence Transformers
- **Dashboard:** Streamlit
- **Vector Store:** FAISS / pgvector

## Setup Instructions

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Ollama (for local LLM)
- Git

### 1. Clone Repository

```bash
cd /home/lenovo/Desktop/New_tech_demo
```

### 2. Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install Ollama & Download Model

```bash
# Install Ollama (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Download Llama 3.1 8B model
ollama pull llama3.1
```

### 5. Setup PostgreSQL Database

```bash
# Install PostgreSQL (if not already installed)
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database
sudo -u postgres psql -c "CREATE DATABASE unilever_poc;"
sudo -u postgres psql -d unilever_poc -c "CREATE EXTENSION vector;"
```

### 6. Configure Environment

```bash
cp .env.example .env
# Edit .env with your database credentials
nano .env
```

### 7. Initialize Database

```bash
python -m database.init_db
```

### 8. Load Data

```bash
python -m database.load_data
```

## Running the Application

### Start API Server

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Access API docs: http://localhost:8000/docs

### Start Dashboard

```bash
streamlit run dashboard/app.py
```

Access dashboard: http://localhost:8501

### Run Tests

```bash
pytest tests/ -v --cov
```

## Development Workflow

### Phase 1: Setup (Week 1)
- Environment setup ✅
- Database creation
- Data loading

### Phase 2: Build Agents (Week 2-3)
- Spend Agent (Text-to-SQL)
- Demand Agent (Text-to-SQL)

### Phase 3: Ground Truth (Week 3-4)
- Query collection (2,500 queries)
- SQL generation

### Phase 4: Evaluation Framework (Week 4-5)
- 6-step evaluation pipeline
- Agent improvement (≥90% accuracy)

### Phase 5: Monitoring Framework (Week 6-7)
- Drift detection
- Error classification

### Phase 6: Integration (Week 8-9)
- API development
- Dashboard creation

### Phase 7: Deployment (Week 10)
- Testing & validation
- Azure deployment

## API Endpoints

- `POST /api/v1/query` - Process query with agent
- `POST /api/v1/evaluate` - Evaluate agent response
- `GET /api/v1/metrics` - Get evaluation metrics
- `GET /api/v1/drift` - Get drift detection status
- `GET /api/v1/errors` - Get error summary
- `POST /api/v1/baseline/update` - Update drift baseline

## Contributing

This is a POC project for Unilever. For issues or questions, contact the development team.

## License

Proprietary - Unilever POC

## Documentation

- [Implementation Plan](Implementation_Plan.md)
- [Dataset Analysis](Dataset_Analysis.md)
- [Architecture Overview](Unilever_POC_Final.pdf)

## Status

🚧 **Phase 1: In Progress** - Setting up infrastructure and loading data

**Last Updated:** February 2, 2026
