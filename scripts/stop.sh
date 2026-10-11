#!/usr/bin/env bash
cd "$(dirname "$0")/.."
for f in logs/server.pid logs/tunnel.pid; do [ -f $f ] && kill "$(cat $f)" 2>/dev/null && echo "stopped $f"; rm -f $f; done
