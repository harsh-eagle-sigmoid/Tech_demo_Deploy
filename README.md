# Unilever Procurement GPT (POC)

**A Multi-Agent AI System for Supply Chain & Procurement Intelligence**

## 📖 Project Abstract
The **Unilever Procurement GPT** is an advanced AI system designed to democratize access to critical supply chain data. Unlike standard chatbots, it uses a governed **Text-to-SQL Architecture** to query enterprise databases with high precision (>90% accuracy). It solves the "Hallucination Problem" by strictly adhering to database schemas and business logic.

### Key Capabilities
-   **Multi-Agent Architecture**: Separate specialized agents for **Spend** (Financials) and **Demand** (Supply Chain).
-   **Real-Time Governance**: Tracks **Drift** (anomalous queries) and **Accuracy** (Ground Truth evaluation) on every request.
-   **Enterprise Security**: Integrated with **Azure Active Directory** for secure access.

---

## 💻 Code Introduction (Architecture)

This project follows a **Modular Microservice-like Monolith** structure:

### 1. The Core (API Gateway)
-   **Path**: `api/main.py`
-   **Role**: The central hub. Handles Authentication, Request Routing, and Logging.
-   **Tech**: FastAPI, Uvicorn.

### 2. The Intelligence (Agents)
-   **Path**: `spend_agent/`, `demand_agent/`
-   **Role**: Independent workers. Each agent runs on its own port (8001, 8002) and contains specific **System Prompts** and **Few-Shot Examples** to master its domain.
-   **Tech**: Azure OpenAI (GPT-4o).

### 3. The Guardian (Monitoring)
-   **Path**: `monitoring/` & `evaluation/`
-   **Role**: Ensures reliability.
    -   **Drift Detector**: Uses Vector Embeddings (AWS Bedrock) to flag weird queries.
    -   **Evaluator**: Automatically grades AI answers against a Ground Truth dataset.

### 4. The Data Layer (Database)
-   **Path**: `database/`
-   **Role**: Stores business data (PostgreSQL) and vector embeddings (`pgvector`).
-   **Key Files**: `schemas.py` (Table Definitions), `load_data.py` (ETL Script).

---

## 🚀 Quick Start

### Prerequisites
-   Python 3.11+
-   PostgreSQL 15+ (with `pgvector`)
-   Node.js 18+ (for Dashboard)

### 1. Setup
```bash
# Clone and Install
git clone <repo>
cd New_tech_demo
pip install -r requirements.txt

# Setup DB
python database/init_db.py
python database/load_data.py
```

### 2. Run Everything
```bash
./start_all.sh
```

### 3. Access
-   **Dashboard**: `http://localhost:3000` (Login Required)
-   **API**: `http://localhost:8000`
-   **Spend Agent UI**: `http://localhost:8501`
-   **Demand Agent UI**: `http://localhost:8502`

---

## 🛠 Tech Stack
-   **Backend**: Python, FastAPI, SQLAlchemy
-   **Database**: PostgreSQL + pgvector
-   **AI Models**: Azure OpenAI (GPT-4o), AWS Titan (Embeddings)
-   **Frontend**: React, Vite, Recharts, Streamlit
