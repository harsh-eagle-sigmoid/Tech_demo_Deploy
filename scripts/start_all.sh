#!/bin/bash

# Kill ports 8000, 8001, 8002, 3000, 8501, 8502 to ensure clean slate
echo "🧹 Killing old processes..."
fuser -k 8000/tcp 2>/dev/null
fuser -k 8001/tcp 2>/dev/null
fuser -k 8002/tcp 2>/dev/null
fuser -k 3000/tcp 2>/dev/null
fuser -k 8501/tcp 2>/dev/null
fuser -k 8502/tcp 2>/dev/null

# Each service uses its own venv
FRAMEWORK_PYTHON="/home/lenovo/New_tech_demo/venv/bin/python3"
SPEND_PYTHON="/home/lenovo/spend_agent/venv/bin/python3"
DEMAND_PYTHON="/home/lenovo/demand_agent/venv/bin/python3"

# Start Spend Agent (FastAPI on port 8001)
echo "🚀 Starting Spend Agent (Port 8001)..."
cd /home/lenovo/spend_agent
nohup $SPEND_PYTHON run.py > logs/spend.log 2>&1 &
SPEND_PID=$!

# Start Spend Agent UI (Streamlit on port 8501)
echo "🎨 Starting Spend Agent UI (Port 8501)..."
nohup $SPEND_PYTHON -m streamlit run streamlit_app.py --server.port 8501 > logs/streamlit_spend.log 2>&1 &
SPEND_UI_PID=$!

# Start Demand Agent (FastAPI on port 8002)
echo "🚀 Starting Demand Agent (Port 8002)..."
cd /home/lenovo/demand_agent
nohup $DEMAND_PYTHON run.py > logs/demand.log 2>&1 &
DEMAND_PID=$!

# Start Demand Agent UI (Streamlit on port 8502)
echo "🎨 Starting Demand Agent UI (Port 8502)..."
nohup $DEMAND_PYTHON -m streamlit run streamlit_app.py --server.port 8502 > logs/streamlit_demand.log 2>&1 &
DEMAND_UI_PID=$!

# Start Framework API (uvicorn on port 8000)
echo "🚀 Starting Framework API (Port 8000)..."
cd /home/lenovo/New_tech_demo
nohup $FRAMEWORK_PYTHON -m uvicorn api.main:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
API_PID=$!

# Start Dashboard (React/Vite on port 5173)
echo "🚀 Starting Dashboard..."
cd /home/lenovo/New_tech_demo/dashboard
nohup npm run dev > logs/dashboard.log 2>&1 &
DASH_PID=$!

echo ""
echo "✅ All services started!"
echo "-----------------------------------"
echo "  Spend Agent API  → http://localhost:8001"
echo "  Spend Agent UI   → http://localhost:8501"
echo "  Demand Agent API → http://localhost:8002"
echo "  Demand Agent UI  → http://localhost:8502"
echo "  Framework API    → http://localhost:8000"
echo "  Dashboard        → http://localhost:5173"
echo "-----------------------------------"
echo "  PIDs: spend=$SPEND_PID spend_ui=$SPEND_UI_PID"
echo "        demand=$DEMAND_PID demand_ui=$DEMAND_UI_PID"
echo "        api=$API_PID dashboard=$DASH_PID"
echo ""
echo "  Tail logs: tail -f /home/lenovo/New_tech_demo/logs/api.log"
echo "             tail -f /home/lenovo/spend_agent/logs/spend.log"
