#!/usr/bin/env bash
set -euo pipefail

# AstroAgent Evaluation Runner
# Spins up the backend, runs the eval harness, prints the scorecard, and cleans up.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
EVAL_DIR="$SCRIPT_DIR/eval"
RESULTS_DIR="$SCRIPT_DIR/results"
PID_FILE="$SCRIPT_DIR/.backend.pid"

cleanup() {
    echo "🧹 Cleaning up..."
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null || true
            wait "$PID" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
    fi
    echo "✅ Done."
}

trap cleanup EXIT INT TERM

echo "🚀 AstroAgent Evaluation Runner"
echo "================================"

# ---- 1️⃣ Install dependencies ----
echo ""
echo "📦 Checking backend dependencies..."
cd "$BACKEND_DIR"
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi
pip install -q -r requirements.txt
echo "✅ Dependencies ready"

# ---- 2️⃣ Create data directory ----
mkdir -p "$BACKEND_DIR/data"
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$RESULTS_DIR"

# ---- 3️⃣ Start backend ----
echo ""
echo "🔧 Starting AstroAgent backend..."
cd "$BACKEND_DIR"
export PYTHONPATH="$BACKEND_DIR:$PYTHONPATH"
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$PID_FILE"
echo "Backend PID: $BACKEND_PID"

# ---- 4️⃣ Wait for health check ----
echo ""
echo "⏳ Waiting for backend to be ready..."
ATTEMPTS=0
MAX_ATTEMPTS=30
until curl -s http://localhost:8000/health | grep -q '"status":"ok"'; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ $ATTEMPTS -ge $MAX_ATTEMPTS ]; then
        echo "❌ Backend failed to start after ${MAX_ATTEMPTS}s"
        exit 1
    fi
    sleep 1
done
echo "✅ Backend is healthy"

# ---- 5️⃣ Run evaluation harness ----
echo ""
echo "🧪 Running evaluation harness..."
cd "$SCRIPT_DIR"
python -m eval.run

# ---- 6️⃣ Print latest scorecard ----
echo ""
echo "📊 Latest Scorecard:"
echo "----------------------"
LATEST_SCORECARD=$(ls -t "$RESULTS_DIR"/*_scorecard.md 2>/dev/null | head -1)
if [ -f "$LATEST_SCORECARD" ]; then
    cat "$LATEST_SCORECARD"
else
    echo "No scorecard generated."
fi

echo ""
echo "================================"
echo "✨ Evaluation complete"
