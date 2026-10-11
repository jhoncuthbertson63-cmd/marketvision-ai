"""Yahoo Finance public endpoints (unofficial, delayed). Chart endpoint needs no auth; quote and
quoteSummary need a cookie+crumb, which we obtain the same way a browser does."""
import asyncio, math, time
import httpx
from ..core import cache
from ..core.config import BROWSER_UA, TTL_QUOTE, TTL_CHART, TTL_SUMMARY, TTL_NEWS
from ..core.http import client, get_retry, SourceUnavailable

SOURCE = "Yahoo Finance (unofficial public endpoints)"
_crumb = {"value": None, "ts": 0, "client": None}
_crumb_lock = asyncio.Lock()


async def _crumb_client(force=False):
    async with _crumb_lock:
        if not force and _crumb["value"] and time.time() - _crumb["ts"] < 3600:
            return _crumb["client"], _crumb["value"]
        c = httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": BROWSER_UA})
        try:
            await c.get("https://fc.yahoo.com")
        except Exception:
            pass
        r = await c.get("https://query2.finance.yahoo.com/v1/test/getcrumb")
        if r.status_code != 200 or not r.text or "<" in r.text:
            raise SourceUnavailable("Yahoo crumb unavailable")
        if _crumb["client"]:
            try:
                await _crumb["client"].aclose()
            except Exception:
                pass
        _crumb.update(value=r.text.strip(), ts=time.time(), client=c)
        return c, _crumb["value"]


async def _auth_get(url, params):
    for attempt in range(2):
        c, crumb = await _crumb_client(force=attempt > 0)
        r = await c.get(url, params={**params, "crumb": crumb})
        if r.status_code in (401, 403):
            continue
        r.raise_for_status()
        return r.json()
    raise SourceUnavailable("Yahoo auth endpoint refused request")


async def quotes(symbols: list[str]) -> dict:
    """Batch quote. Returns {symbol: quote_dict}."""
    symbols = [s.upper() for s in symbols]
    key = "yq:" + ",".join(sorted(set(symbols)))

    async def fetch():
        out = {}
        for i in range(0, len(symbols), 50):
            chunk = symbols[i:i + 50]
            j = await _auth_get("https://query2.finance.yahoo.com/v7/finance/quote", {"symbols": ",".join(chunk)})
            for q in (j.get("quoteResponse") or {}).get("result") or []:
                out[q["symbol"]] = q
        if not out:
            raise SourceUnavailable("empty quote response")
        return out
    val, ts, _, stale = await cache.cached(key, TTL_QUOTE, fetch, disk=True)
    return {"data": val, "fetched_at": ts, "stale": stale}


async def chart(symbol: str, rng="5y", interval="1d") -> dict:
    key = f"ych:{symbol}:{rng}:{interval}"

    async def fetch():
        r = await get_retry(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                            params={"range": rng, "interval": interval, "includeAdjustedClose": "true"})
        res = r.json()["chart"]["result"][0]
        ts = res.get("timestamp") or []
        q = res["indicators"]["quote"][0]
        adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose") or q.get("close")
        rows = []
        for i, t in enumerate(ts):
            c = q["close"][i]
            if c is None:
                continue
            rows.append([t, q["open"][i], q["high"][i], q["low"][i], c, q["volume"][i], adj[i] if adj else c])
        m = res["meta"]
        return {"meta": {k: m.get(k) for k in ("symbol", "currency", "regularMarketPrice", "regularMarketTime",
                                               "chartPreviousClose", "longName", "shortName", "exchangeName",
                                               "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "regularMarketVolume",
                                               "instrumentType", "exchangeTimezoneName")}, "rows": rows}
    try:
        val, ts, _, stale = await cache.cached(key, TTL_CHART, fetch)
        return {"data": val, "fetched_at": ts, "stale": stale, "source": SOURCE,
                "url": f"https://finance.yahoo.com/quote/{symbol}/history"}
    except Exception:
        from . import stooq
        return await stooq.chart(symbol)


async def summary(symbol: str, modules: str) -> dict:
    key = f"ysum:{symbol}:{modules}"

    async def fetch():
        j = await _auth_get(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}", {"modules": modules})
        res = (j.get("quoteSummary") or {}).get("result")
        if not res:
            raise SourceUnavailable("no quoteSummary")
        return res[0]
    val, ts, _, stale = await cache.cached(key, TTL_SUMMARY, fetch)
    return {"data": val, "fetched_at": ts, "stale": stale}


async def search_news(symbol: str, n=10) -> dict:
    key = f"ynews:{symbol}:{n}"

    async def fetch():
        r = await client().get("https://query2.finance.yahoo.com/v1/finance/search",
                               params={"q": symbol, "newsCount": n, "quotesCount": 1})
        r.raise_for_status()
        j = r.json()
        return {"news": [{"title": x.get("title"), "publisher": x.get("publisher"), "link": x.get("link"),
                          "time": x.get("providerPublishTime"), "related": x.get("relatedTickers")}
                         for x in j.get("news") or []],
                "quote": (j.get("quotes") or [None])[0]}
    val, ts, _, stale = await cache.cached(key, TTL_NEWS, fetch)
    return {"data": val, "fetched_at": ts, "stale": stale}


async def peers(symbol: str) -> list[str]:
    key = f"ypeers:{symbol}"

    async def fetch():
        r = await client().get(f"https://query2.finance.yahoo.com/v6/finance/recommendationsbysymbol/{symbol}")
        r.raise_for_status()
        res = r.json()["finance"]["result"]
        return [x["symbol"] for x in (res[0]["recommendedSymbols"] if res else [])]
    try:
        val, *_ = await cache.cached(key, 86400, fetch)
        return val
    except Exception:
        return []


def raw(v):
    if isinstance(v, dict):
        return v.get("raw")
    return v


# ---------- performance math on chart rows ----------
def perf_from_rows(rows, last_price=None):
    """rows: [ts, o, h, l, c, v, adj]. Returns returns over standard windows using adjusted close
    (total-return-ish for ETFs). Windows by calendar offset from last bar."""
    if not rows:
        return {}
    closes = [(r[0], r[6] if r[6] is not None else r[4]) for r in rows]
    t_last, c_last = closes[-1]

    def back(days):
        target = t_last - days * 86400
        prev = None
        for t, c in closes:
            if t <= target:
                prev = c
            else:
                break
        return prev

    def ret(p):
        return None if not p else (c_last / p - 1) * 100
    import datetime as dt
    y0 = dt.datetime.fromtimestamp(t_last).replace(month=1, day=1, hour=0, minute=0).timestamp()
    ytd_base = None
    for t, c in closes:
        if t < y0:
            ytd_base = c
    out = {"1d": ret(closes[-2][1]) if len(closes) > 1 else None, "1w": ret(back(7)), "1m": ret(back(30)),
           "3m": ret(back(91)), "6m": ret(back(182)), "ytd": ret(ytd_base), "1y": ret(back(365)),
           "3y": ret(back(365 * 3)), "5y": ret(back(365 * 5 - 3))}
    # trend & risk
    cl = [c for _, c in closes]
    out["sma50"] = sum(cl[-50:]) / min(50, len(cl))
    out["sma200"] = sum(cl[-200:]) / min(200, len(cl))
    out["above50"] = cl[-1] > out["sma50"]
    out["above200"] = cl[-1] > out["sma200"]
    rets = [cl[i] / cl[i - 1] - 1 for i in range(max(1, len(cl) - 252), len(cl)) if cl[i - 1]]
    if len(rets) > 20:
        mu = sum(rets) / len(rets)
        out["vol_1y"] = math.sqrt(sum((x - mu) ** 2 for x in rets) / (len(rets) - 1)) * math.sqrt(252) * 100
    peak, mdd = 0, 0
    for c in cl[-252 * 3:]:
        peak = max(peak, c)
        mdd = min(mdd, c / peak - 1)
    out["max_dd_3y"] = mdd * 100
    out["last_bar"] = t_last
    return out
