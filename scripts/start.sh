#!/usr/bin/env bash
# Start MarketVision API+web server in the background (idempotent).
cd "$(dirname "$0")/.."
PORT=${PORT:-8810}
if [ -f logs/server.pid ] && kill -0 "$(cat logs/server.pid)" 2>/dev/null; then echo "server already running (pid $(cat logs/server.pid))"; exit 0; fi
[ -f .env ] && set -a && . ./.env && set +a
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 > logs/server.log 2>&1 &
echo $! > logs/server.pid
echo "server started pid $(cat logs/server.pid) on :$PORT"
