# MarketVision AI — Stage 1

Research-first market intelligence platform. FastAPI backend + dependency-free ES-module frontend (ECharts vendored).

## Run
    ./scripts/start.sh            # server on :8810 (nohup, pid in logs/server.pid)
    ./scripts/stop.sh             # stop server + tunnel
    setsid nohup ./scripts/watchdog.sh &   # auto-restart server (WATCH_TUNNEL=1 to also keep tunnel)
    ./scripts/tunnel.sh           # public URL: ngrok if NGROK_AUTHTOKEN set, else cloudflared quick tunnel
Logs: logs/server.log, logs/tunnel.log. Cache: data/cache (delete to force refresh).

## Architecture
    app/core/        config, two-tier TTL cache (memory + disk, single-flight, stale-on-error), HTTP clients, LLM adapter
    app/providers/   sec.py (EDGAR tickers/submissions/companyfacts → distilled XBRL), yahoo.py (chart/quote/quoteSummary/news),
                     fred.py (public CSV), nasdaq.py (earnings + economic calendars), stooq.py (price fallback)
    app/analysis/    fundamentals.py (10-yr table, TTM, split adjustment, balance sheet, capital allocation),
                     scenarios.py (bull/base/bear formula engine), narrative.py (rule-based evidence-tagged text), universe.py
    app/modules/     dashboard.py, research.py, scanner.py — FastAPI routers; registry.py lists every module (live + planned)
    static/js/       app.js (router/nav from /api/modules), ui.js (formatting, source footers, evidence labels, charts),
                     modules/<id>.js (one per page; planned.js renders 'Coming in a later stage' slots)
Add a later-stage module: write app/modules/<id>.py with a router, flip its registry entry to status "live", add static/js/modules/<id>.js and register it in app.js LIVE.

## Data rules
Every panel carries {source, url, fetched_at, as_of, delayed, stale, kind}. Evidence kinds: fact, derived, estimate, model, editorial, ai, news.
Upstream failure → explicit "Data unavailable" state (or stale cache, flagged). Market-size figures only from data/market_sizes.json with a cited URL.
