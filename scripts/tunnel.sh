#!/usr/bin/env bash
# Expose the app publicly.
#  - If NGROK_AUTHTOKEN is set (free ngrok account), uses ngrok over TLS/443 (works from this box).
#  - Otherwise tries a Cloudflare quick tunnel (no account) — NOTE: this box's egress blocks
#    port 7844, which cloudflared requires, so it will not connect here; it works on normal networks.
cd "$(dirname "$0")/.."
PORT=${PORT:-8810}
[ -f .env ] && set -a && . ./.env && set +a
if [ -f logs/tunnel.pid ] && kill -0 "$(cat logs/tunnel.pid)" 2>/dev/null; then echo "tunnel already running: $(cat logs/public_url.txt 2>/dev/null)"; exit 0; fi
if [ -n "$NGROK_AUTHTOKEN" ]; then
  ~/bin/ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null
  nohup ~/bin/ngrok http "$PORT" --log stdout > logs/tunnel.log 2>&1 &
  echo $! > logs/tunnel.pid
  for i in $(seq 1 30); do U=$(grep -o 'url=https://[^ ]*' logs/tunnel.log | head -1 | cut -d= -f2); [ -n "$U" ] && break; sleep 1; done
else
  nohup ~/bin/cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" > logs/tunnel.log 2>&1 &
  echo $! > logs/tunnel.pid
  for i in $(seq 1 30); do U=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' logs/tunnel.log | head -1); [ -n "$U" ] && break; sleep 1; done
fi
echo "${U:-tunnel URL not found; see logs/tunnel.log}"; echo "$U" > logs/public_url.txt
