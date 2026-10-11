#!/usr/bin/env bash
# Keeps the server alive (and the tunnel too when WATCH_TUNNEL=1). Run: setsid nohup scripts/watchdog.sh &
cd "$(dirname "$0")/.."
while true; do
  if ! { [ -f logs/server.pid ] && kill -0 "$(cat logs/server.pid)" 2>/dev/null; }; then ./scripts/start.sh >> logs/watchdog.log 2>&1; fi
  if [ "${WATCH_TUNNEL:-0}" = 1 ] && ! { [ -f logs/tunnel.pid ] && kill -0 "$(cat logs/tunnel.pid)" 2>/dev/null; }; then ./scripts/tunnel.sh >> logs/watchdog.log 2>&1; fi
  sleep 30
done
