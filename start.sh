#!/bin/bash
# 1. Start Temporal Server (Background)
echo "--- 🕒 Starting Temporal... ---"
/root/.temporalio/bin/temporal server start-dev --ip 0.0.0.0 --ui-port 8080 &
sleep 10

# 2. Run Ingestion (Database Setup)
echo "--- 📚 Checking Database... ---"
python src/ingest.py

# 3. Start Worker (Background)
echo "--- 👷 Starting Worker... ---"
python worker.py &

# 4. Start API (Foreground - keeps container running)
echo "--- 🚀 Starting API... ---"
uvicorn main:app --host 0.0.0.0 --port 10000
