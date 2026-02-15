#!/bin/bash

# Kill ports 8000, 8001, 8002, 3000, 8501, 8502 to ensure clean slate
echo "🧹 Killing old processes..."
fuser -k 8000/tcp 2>/dev/null
fuser -k 8001/tcp 2>/dev/null
fuser -k 8002/tcp 2>/dev/null
fuser -k 3000/tcp 2>/dev/null
fuser -k 8501/tcp 2>/dev/null
fuser -k 8502/tcp 2>/dev/null

# Activate venv python path
PYTHON_EXEC="/home/lenovo/New_tech_demo/venv/bin/python"
STREAMLIT_EXEC="/home/lenovo/New_tech_demo/venv/bin/streamlit"

# Start Spend Agent
echo "🚀 Starting Spend Agent (Port 8001)..."
cd /home/lenovo/spend_agent
nohup $PYTHON_EXEC run.py > spend.log 2>&1 &
SPEND_PID=$!

# Start Spend Agent UI
echo "🎨 Starting Spend Agent UI (Port 8501)..."
nohup $PYTHON_EXEC -m streamlit run streamlit_app.py --server.port 8501 > streamlit_spend.log 2>&1 &
SPEND_UI_PID=$!

# Start Demand Agent
echo "🚀 Starting Demand Agent (Port 8002)..."
cd /home/lenovo/demand_agent
nohup $PYTHON_EXEC run.py > demand.log 2>&1 &
DEMAND_PID=$!

# Start Demand Agent UI
echo "🎨 Starting Demand Agent UI (Port 8502)..."
nohup $PYTHON_EXEC -m streamlit run streamlit_app.py --server.port 8502 > streamlit_demand.log 2>&1 &
DEMAND_UI_PID=$!

# Start API Gateway
echo "🚀 Starting API Gateway (Port 8000)..."
cd /home/lenovo/New_tech_demo
nohup $PYTHON_EXEC -m api.main > logs/api.log 2>&1 &
API_PID=$!

# Start Dashboard
echo "🚀 Starting Dashboard (Port 3000)..."
cd /home/lenovo/New_tech_demo/dashboard
nohup npm run dev > dashboard.log 2>&1 &
DASH_PID=$!

echo "✅ All services started!"
echo "-----------------------------------"
echo "Spend Agent PID: $SPEND_PID"
echo "Spend UI PID:    $SPEND_UI_PID"
echo "Demand Agent PID: $DEMAND_PID"
echo "Demand UI PID:    $DEMAND_UI_PID"
echo "API Gateway PID: $API_PID"
echo "Dashboard PID: $DASH_PID"
echo "-----------------------------------"
echo "monitor logs with: tail -f */*.log"
