#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Load project .env (ensures Neo4j password etc. match docker-compose)
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

echo "=== SciNova OS Startup ==="

free_port() {
  local port=$1
  local pids
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "Port $port in use — stopping existing process(es)..."
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

free_port 8000
free_port 5173

# Backend setup
if [ ! -d "backend/venv" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv backend/venv
fi

source backend/venv/bin/activate
pip install -q -r backend/requirements.txt

mkdir -p backend/storage/uploads

# Start backend
echo "Starting FastAPI backend on :8000..."
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd "$ROOT"

# Frontend setup
if [ ! -d "frontend/node_modules" ]; then
  echo "Installing frontend dependencies..."
  cd frontend && npm install && cd "$ROOT"
fi

echo "Starting React frontend on :5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd "$ROOT"

echo ""
echo "SciNova OS is running:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "Login: scientist / sci123"
echo ""
echo "Press Ctrl+C to stop."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
