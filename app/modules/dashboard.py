import datetime as dt
from fastapi import APIRouter
from ..providers import yahoo, fred, nasdaq
from ..analysis.universe import HEATMAP, INDEXES, SECTOR_ETFS
from .common import M, iso, delay_label, gather_limited, ET

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
YURL = "https://finance.yahoo.com/quote/{}"


def _spark(rows, n=120):
    rows = rows[-252:]
    step = max(1, len(rows) // n)
    pts = rows[::step]
    if pts and pts[-1] is not rows[-1]:
        pts.append(rows[-1])
    return [[r[0] * 1000, round(r[4], 4)] for r in pts]


async def _instrument(sym, name, quote=None, spark=True):
    ch = await yahoo.chart(sym, "5y", "1d")
    rows = ch["data"]["rows"]
    perf = yahoo.perf_from_rows(rows)
    m = ch["data"]["meta"]
    price = (quote or {}).get("regularMarketPrice") or m.get("regularMarketPrice")
    chg = (quote or {}).get("regularMarketChangePercent")
    if chg is not None:
        perf["1d"] = chg
    return {"symbol": sym, "name": name, "price": price, "perf": perf, "spark": _spark(rows) if spark else None,
            "meta": M(ch.get("source", yahoo.SOURCE), ch.get("url"), ch["fetched_at"], delayed=delay_label(quote),
                      stale=ch["stale"], as_of=iso(m.get("regularMarketTime")))}


@router.get("/indexes")
async def indexes():
    syms = [s for s, _ in INDEXES] + ["^VIX", "SPY", "RSP", "QQQ", "DIA", "IWM"]
    names = dict(INDEXES) | {"^VIX": "CBOE Volatility Index", "SPY": "SPDR S&P 500 ETF", "RSP": "Equal-Weight S&P 500 ETF",
                             "QQQ": "Invesco QQQ (Nasdaq-100)", "DIA": "SPDR Dow ETF", "IWM": "iShares Russell 2000 ETF"}
    try:
        qs = (await yahoo.quotes(syms))["data"]
    except Exception:
        qs = {}
    res = await gather_limited([_instrument(s, names[s], qs.get(s)) for s in syms])
    items = []
    for s, r in zip(syms, res):
        if isinstance(r, Exception):
            items.append({"symbol": s, "name": names[s], "error": f"data unavailable: {type(r).__name__}"})
        else:
            items.append(r)
    by = {i["symbol"]: i for i in items}
    breadth_proxy = None
    if "perf" in by.get("RSP", {}) and "perf" in by.get("SPY", {}):
        breadth_proxy = {k: (by["RSP"]["perf"].get(k) or 0) - (by["SPY"]["perf"].get(k) or 0) for k in ("1m", "3m", "ytd", "1y")}
    return {"items": items, "rsp_minus_spy": breadth_proxy,
            "rsp_note": "Equal-weight (RSP) minus cap-weight (SPY) return, percentage points. Positive = the average stock is beating the mega-caps (broadening); negative = narrow, mega-cap-led market."}


@router.get("/sectors")
async def sectors():
    syms = [s for s, _ in SECTOR_ETFS] + ["SPY"]
    try:
        qs = (await yahoo.quotes(syms))["data"]
    except Exception:
        qs = {}
    res = await gather_limited([_instrument(s, n, qs.get(s), spark=False) for s, n in SECTOR_ETFS + [("SPY", "S&P 500")]])
    spy = res[-1] if not isinstance(res[-1], Exception) else None
    out = []
    for (s, n), r in zip(SECTOR_ETFS, res[:-1]):
        if isinstance(r, Exception):
            out.append({"symbol": s, "name": n, "error": "data unavailable"})
            continue
        if spy:
            p, sp = r["perf"], spy["perf"]
            r["rs"] = {k: (p.get(k) or 0) - (sp.get(k) or 0) for k in ("1w", "1m", "3m", "6m", "1y")}
            # rotation quadrant: x = 3m relative strength (trend), y = 1m RS minus (3m RS/3) (momentum of RS)
            x, y = r["rs"]["3m"], r["rs"]["1m"] - r["rs"]["3m"] / 3
            r["rotation"] = {"x": x, "y": y, "quadrant": ("Leading" if x >= 0 and y >= 0 else "Weakening" if x >= 0 else
                                                          "Improving" if y >= 0 else "Lagging")}
        out.append(r)
    return {"items": out, "rotation_rule": "x = 3-month return minus SPY (relative trend). y = 1-month relative return minus one-third of 3-month relative return (is relative strength accelerating?). Leading: x≥0,y≥0 · Weakening: x≥0,y<0 · Improving: x<0,y≥0 · Lagging: x<0,y<0. Capital-flow inference is based on relative price performance, not fund-flow data.",
            "meta": spy["meta"] if spy else M(yahoo.SOURCE, None, None, note="data unavailable")}


MACRO = [
    ("DFF", "Fed Funds Effective Rate", "%", "daily"), ("DGS3MO", "3-Month Treasury", "%", "daily"),
    ("DGS2", "2-Year Treasury", "%", "daily"), ("DGS10", "10-Year Treasury", "%", "daily"),
    ("T10Y2Y", "10Y–2Y Spread", "pp", "daily"), ("BAMLH0A0HYM2", "High-Yield Credit Spread (ICE BofA)", "%", "daily"),
    ("VIXCLS", "VIX (close)", "", "daily"), ("CPIAUCSL", "CPI Inflation (YoY)", "%", "monthly"),
    ("UNRATE", "Unemployment Rate", "%", "monthly"), ("ICSA", "Initial Jobless Claims", "", "weekly"),
    ("A191RL1Q225SBEA", "Real GDP Growth (QoQ annualized)", "%", "quarterly"), ("DCOILWTICO", "WTI Crude Oil", "$", "daily"),
]


async def _macro_one(sid, name, unit, freq):
    s = await fred.series(sid)
    d = s["data"]
    if sid == "CPIAUCSL":  # convert index level to YoY %
        idx = {k: v for k, v in d}
        yoy = []
        for k, v in d:
            prev = f"{int(k[:4]) - 1}{k[4:]}"
            if prev in idx:
                yoy.append([k, (v / idx[prev] - 1) * 100])
        d = yoy
    tail = d[-260:] if freq == "daily" else d[-60:] if freq != "quarterly" else d[-40:]
    last, prev = d[-1], (d[-2] if len(d) > 1 else None)
    yr = None
    for k, v in reversed(d):
        if k <= f"{int(last[0][:4]) - 1}{last[0][4:]}":
            yr = v
            break
    return {"id": sid, "name": name, "unit": unit, "freq": freq, "value": last[1], "date": last[0],
            "change": last[1] - prev[1] if prev else None, "change_1y": last[1] - yr if yr is not None else None,
            "series": tail, "meta": M("FRED, Federal Reserve Bank of St. Louis", s["url"], s["fetched_at"], stale=s["stale"],
                                       as_of=last[0], note="Official data; published with a lag" + (" (CPI YoY computed from index)" if sid == "CPIAUCSL" else ""))}


@router.get("/macro")
async def macro():
    res = await gather_limited([_macro_one(*m) for m in MACRO], 6)
    return {"items": [r if not isinstance(r, Exception) else {"id": m[0], "name": m[1], "error": "data unavailable (FRED request failed)"}
                      for m, r in zip(MACRO, res)]}


@router.get("/heatmap")
async def heatmap():
    syms = [s for lst in HEATMAP.values() for s in lst]
    try:
        qr = await yahoo.quotes(syms)
    except Exception as e:
        return {"error": f"Quote data unavailable from Yahoo Finance ({type(e).__name__}).", "items": []}
    qs = qr["data"]
    charts = await gather_limited([yahoo.chart(s, "1y", "1d") for s in syms], 10)
    items = []
    for s, ch in zip(syms, charts):
        q = qs.get(s)
        if not q:
            continue
        sector = next(k for k, v in HEATMAP.items() if s in v)
        perf = yahoo.perf_from_rows(ch["data"]["rows"]) if not isinstance(ch, Exception) else {}
        avgv = q.get("averageDailyVolume3Month")
        items.append({"symbol": s, "name": q.get("shortName"), "sector": sector, "market_cap": q.get("marketCap"),
                      "price": q.get("regularMarketPrice"), "chg_1d": q.get("regularMarketChangePercent"),
                      "chg_1w": perf.get("1w"), "chg_1m": perf.get("1m"), "chg_ytd": perf.get("ytd"),
                      "chg_52w": q.get("fiftyTwoWeekChangePercent"), "volume": q.get("regularMarketVolume"), "avg_volume_3m": avgv,
                      "rel_volume": (q.get("regularMarketVolume") or 0) / avgv if avgv else None,
                      "pct_from_52w_high": q.get("fiftyTwoWeekHighChangePercent"), "above50": perf.get("above50"),
                      "above200": perf.get("above200"), "fwd_pe": q.get("forwardPE"), "trailing_pe": q.get("trailingPE")})
    n = len(items)
    with_trend = [i for i in items if i["above50"] is not None]
    adv = sum(1 for i in items if (i["chg_1d"] or 0) > 0)
    breadth = {"universe": n, "advancers": adv, "decliners": sum(1 for i in items if (i["chg_1d"] or 0) < 0),
               "pct_above_50dma": 100 * sum(1 for i in with_trend if i["above50"]) / len(with_trend) if with_trend else None,
               "pct_above_200dma": 100 * sum(1 for i in with_trend if i["above200"]) / len(with_trend) if with_trend else None,
               "near_52w_high": sum(1 for i in items if i["pct_from_52w_high"] is not None and i["pct_from_52w_high"] > -0.03 * 100 / 100 * 1),
               "note": f"Computed from MarketVision's {n}-stock large-cap universe (not the full NYSE/Nasdaq). Full-market breadth needs an exchange-wide data feed."}
    breadth["near_52w_high"] = sum(1 for i in items if i["pct_from_52w_high"] is not None and i["pct_from_52w_high"] > -3)
    unusual = sorted([i for i in items if i["rel_volume"]], key=lambda i: -i["rel_volume"])[:10]
    movers = sorted([i for i in items if i["chg_1d"] is not None], key=lambda i: i["chg_1d"])
    momentum = sorted([i for i in items if i["chg_1m"] is not None], key=lambda i: -i["chg_1m"])[:10]
    anyq = next(iter(qs.values()))
    return {"items": items, "breadth": breadth, "unusual_volume": unusual, "gainers": movers[::-1][:8], "losers": movers[:8],
            "momentum_1m": momentum, "meta": M(yahoo.SOURCE, "https://finance.yahoo.com/markets/stocks/most-active/", qr["fetched_at"],
                                                 delayed=delay_label(anyq), stale=qr["stale"], as_of=iso(anyq.get("regularMarketTime")),
                                                 note="Sector grouping is MarketVision's editorial classification.")}


def _next_days(n):
    d = dt.datetime.now(ET).date()
    out = []
    while len(out) < n:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return out


@router.get("/calendar")
async def calendar(min_cap_bn: float = 10):
    today = dt.datetime.now(ET).date()
    days = [today] if today.weekday() < 5 else []
    days += _next_days(7)
    days = sorted(set(days))[:7]
    er = await gather_limited([nasdaq.earnings(d) for d in days], 4)
    ec = await gather_limited([nasdaq.economic(d) for d in days], 4)
    earnings, econ, errors = [], [], []
    for d, r in zip(days, er):
        if isinstance(r, Exception):
            errors.append(f"earnings {d}: unavailable")
        else:
            earnings += [x for x in r["data"] if (x["market_cap"] or 0) >= min_cap_bn * 1e9]
    for d, r in zip(days, ec):
        if isinstance(r, Exception):
            errors.append(f"economic {d}: unavailable")
        else:
            econ += [x for x in r["data"] if x["country"] == "United States"]
    earnings.sort(key=lambda x: (x["date"], -(x["market_cap"] or 0)))
    now = dt.datetime.now().timestamp()
    return {"earnings": earnings[:60], "economic": econ[:80], "errors": errors, "days": [d.isoformat() for d in days],
            "meta_earnings": M("Nasdaq.com earnings calendar (public JSON)", "https://www.nasdaq.com/market-activity/earnings", now,
                               kind="estimate", note=f"EPS forecasts are analyst consensus (Zacks via Nasdaq). Filtered to market cap ≥ ${min_cap_bn:.0f}B."),
            "meta_econ": M("Nasdaq.com economic calendar (public JSON)", "https://www.nasdaq.com/market-activity/economic-calendar", now,
                           note="Times are GMT. Consensus values are economist estimates.")}
