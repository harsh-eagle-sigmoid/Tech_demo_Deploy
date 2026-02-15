# Codebase Overview

## 📂 Directory Structure

The codebase is organized into modular "Micro-Services":

### 1. `api/` ( The Gateway)
-   **`main.py`**: The entry point. A **FastAPI** application that routes user requests to the correct agent. It handles **User Authentication** (Azure AD) and centralized logging.

### 2. `agents/` (The Intelligence)
-   **`spend_agent/agent.py`**: Contains the logic for the Spend Expert.
-   **`demand_agent/agent.py`**: Contains the logic for the Demand Expert.
-   **`base_agent.py`**: A shared parent class that handles common tasks like connecting to the LLM (Azure OpenAI).

### 3. `database/` (The Data Layer)
-   **`schemas.py`**: Defines the SQL tables (e.g., `spend_data.orders`, `demand_data.suppliers`).
-   **`load_data.py`**: A script to load the CSV demo data into PostgreSQL.
-   **`connection.py`**: Manages the connection pool to the database to ensure performance.

### 4. `monitoring/` (The Guardian)
-   **`monitor.py`**: Captures logs of every interaction.
-   **`drift_detector.py`**: Uses **Vector Embeddings** (AWS Bedrock) to compare new queries against a "Baseline" of normal queries. If a query is too different (Drift), it alerts the team.
-   **`error_classifier.py`**: Categorizes errors (e.g., "Connection Failed", "Invalid SQL") for easier debugging.

### 5. `dashboard/` (The Frontend)
-   A **React/Vite** application that visualizes the system's performance. It shows graphs of Accuracy, Latency, and Error Rates in real-time.

## 🛠 Key Technologies
-   **Language**: Python 3.11
-   **Database**: PostgreSQL + `pgvector` extension
-   **AI**: Azure OpenAI (GPT-4o) & AWS Titan (Embeddings)
-   **Framework**: FastAPI (Backend) & React (Frontend)
