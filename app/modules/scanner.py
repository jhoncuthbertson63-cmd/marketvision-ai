"""Future Growth Opportunity Scanner: ranks industries by measurable evidence.
Evidence = constituent revenue growth from SEC filings + thematic-ETF price trend/risk from Yahoo +
analyst forward P/E from Yahoo. Scoring formula is published in the response."""
import json, statistics, time
from fastapi import APIRouter
from ..core import cache
from ..core.config import TTL_SCANNER, DATA_DIR
from ..providers import yahoo, sec
from ..analysis import fundamentals as fundmod
from ..analysis.universe import INDUSTRIES, RADAR
from .common import M, iso, gather_limited

router = APIRouter(prefix="/api/scanner", tags=["scanner"])

FORMULA = {
    "percentile": "p(x) = percentile rank of x across the industries scanned (0–100).",
    "growth": "Growth Evidence = 0.35·p(median TTM revenue YoY) + 0.25·p(median 3-yr revenue CAGR) + 0.20·p(median acceleration) + 0.20·p(ETF 6-mo return vs SPY)",
    "acceleration": "Acceleration = TTM revenue YoY − 3-yr revenue CAGR (per company, then median). Positive = growth speeding up.",
    "valuation": "Valuation Attractiveness = 0.4·(100 − p(median forward P/E)) + 0.3·(100 − p(growth-adjusted P/E)) + 0.3·(100 − p(median price/sales)). growth-adj P/E = median fwd P/E ÷ max(median TTM growth, 1). If fewer than half of constituents have positive forward earnings, P/E is 'not meaningful' and both P/E components use the P/S percentile instead.",
    "risk": "Investment Risk = 0.5·p(ETF 1-yr volatility) + 0.3·p(|ETF 3-yr max drawdown|) + 0.2·(100 − p(% of constituents profitable))",
    "composite": "Opportunity Rank Score = 0.5·Growth + 0.3·Valuation + 0.2·(100 − Risk)",
    "stage": "Declining: median 3-yr CAGR < 0, or TTM YoY < 0 and ETF 1-yr RS < −10pp · Early-stage: 3-yr CAGR ≥ 20% and < 60% of constituents profitable · Expanding: 3-yr CAGR ≥ 8% or TTM YoY ≥ 10% · otherwise Mature",
    "signal": "Accelerating if median acceleration > +2pp and ETF 3-mo RS > 0; Slowing if acceleration < −5pp or ETF 3-mo RS < −5pp; else Steady.",
}


def _med(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None


def _pctile(vals):
    clean = [v for v in vals if v is not None]
    out = []
    for v in vals:
        if v is None:
            out.append(50.0)  # neutral when evidence missing (flagged in UI)
            continue
        below = sum(1 for x in clean if x < v)
        eq = sum(1 for x in clean if x == v)
        out.append(100 * (below + 0.5 * (eq - 1)) / max(1, len(clean) - 1) if len(clean) > 1 else 50.0)
    return out


async def _company(sym, quotes):
    info = await sec.lookup(sym)
    q = quotes.get(sym) or {}
    base = {"symbol": sym, "name": q.get("shortName") or (info or {}).get("name"), "market_cap": q.get("marketCap"),
            "fwd_pe": q.get("forwardPE"), "pe": q.get("trailingPE"), "chg_52w": q.get("fiftyTwoWeekChangePercent"),
            "price": q.get("regularMarketPrice")}
    base["ps"] = None
    if not info:
        return {**base, "error": "not in SEC EDGAR"}
    f = (await sec.facts(info["cik"]))["data"]
    fb = fundmod.build(f)
    if fb["currency"] != "USD":
        return {**base, "error": f"financials in {fb['currency']}"}
    rows = fb["rows"]
    agg = {r["fy"]: r["revenue"] for r in rows if r.get("revenue")}
    g = fb["growth"]
    yoy = g.get("revenue_ttm_yoy", g.get("revenue_yoy_latest_fy"))
    c3 = g.get("revenue_cagr_3y")
    rt = fb["ttm"].get("revenue")
    base["ps"] = base["market_cap"] / rt if base["market_cap"] and rt and rt > 0 else None
    return {**base, "revenue_ttm": rt, "revenue_ttm_yoy": yoy, "revenue_cagr_3y": c3,
            "revenue_cagr_5y": g.get("revenue_cagr_5y"), "acceleration": yoy - c3 if yoy is not None and c3 is not None else None,
            "net_margin_ttm": fb["ttm"].get("net_margin"), "annual_revenue": agg}


async def _compute():
    etfs = sorted({i["etf"] for i in INDUSTRIES} | {"SPY"})
    syms = sorted({c for i in INDUSTRIES for c in i["companies"]})
    try:
        quotes = (await yahoo.quotes(syms + etfs))["data"]
    except Exception:
        quotes = {}
    charts = dict(zip(etfs, await gather_limited([yahoo.chart(e, "5y", "1d") for e in etfs], 8)))
    comps = dict(zip(syms, await gather_limited([_company(s, quotes) for s in syms], 5)))
    perf = {e: (yahoo.perf_from_rows(c["data"]["rows"]) if not isinstance(c, Exception) else {}) for e, c in charts.items()}
    spy = perf.get("SPY", {})
    try:
        sizes = json.loads((DATA_DIR / "market_sizes.json").read_text())
    except Exception:
        sizes = {}
    out = []
    for ind in INDUSTRIES:
        cs = []
        for s in ind["companies"]:
            c = comps.get(s)
            cs.append(c if isinstance(c, dict) else {"symbol": s, "error": "data unavailable"})
        ok = [c for c in cs if "revenue_ttm_yoy" in c]
        ep = perf.get(ind["etf"], {})
        rs = lambda k: (ep.get(k) - spy.get(k)) if ep.get(k) is not None and spy.get(k) is not None else None
        prof = [c for c in ok if c.get("net_margin_ttm") is not None]
        # constituent revenue aggregate (same-company set across years, last 6 FY)
        years = sorted({y for c in ok for y in c["annual_revenue"]})[-7:-0 or None]
        full = [c for c in ok if all(y in c["annual_revenue"] for y in years[-6:])] if years else []
        agg = [[y, sum(c["annual_revenue"][y] for c in full)] for y in years[-6:]] if full else []
        agg_cagr = fundmod.cagr(agg[0][1], agg[-1][1], len(agg) - 1) if len(agg) >= 3 else None
        ev = {"median_rev_ttm_yoy": _med([c["revenue_ttm_yoy"] for c in ok]), "median_rev_cagr_3y": _med([c.get("revenue_cagr_3y") for c in ok]),
              "median_rev_cagr_5y": _med([c.get("revenue_cagr_5y") for c in ok]), "median_acceleration": _med([c.get("acceleration") for c in ok]),
              "median_fwd_pe": _med([c["fwd_pe"] for c in ok if c.get("fwd_pe") and c["fwd_pe"] > 0]),
              "median_net_margin": _med([c["net_margin_ttm"] for c in prof]),
              "median_ps": _med([c.get("ps") for c in ok]),
              "pe_coverage": sum(1 for c in ok if c.get("fwd_pe") and c["fwd_pe"] > 0) / len(ok) if ok else 0,
              "pct_profitable": 100 * sum(1 for c in prof if c["net_margin_ttm"] > 0) / len(prof) if prof else None,
              "aggregate_revenue": agg, "aggregate_revenue_cagr": agg_cagr, "aggregate_companies": [c["symbol"] for c in full],
              "etf": {"symbol": ind["etf"], "name": (quotes.get(ind["etf"]) or {}).get("longName"), **{k: ep.get(k) for k in ("1m", "3m", "6m", "ytd", "1y", "3y", "5y", "vol_1y", "max_dd_3y", "above200")},
                      "rs_3m": rs("3m"), "rs_6m": rs("6m"), "rs_1y": rs("1y")},
              "coverage": f"{len(ok)}/{len(cs)} companies with SEC revenue data"}
        e = ev
        if e["median_rev_cagr_3y"] is not None and (e["median_rev_cagr_3y"] < 0 or ((e["median_rev_ttm_yoy"] or 0) < 0 and (e["etf"]["rs_1y"] or 0) < -10)):
            stage = "Declining"
        elif (e["median_rev_cagr_3y"] or 0) >= 20 and (e["pct_profitable"] if e["pct_profitable"] is not None else 100) < 60:
            stage = "Early-stage"
        elif (e["median_rev_cagr_3y"] or 0) >= 8 or (e["median_rev_ttm_yoy"] or 0) >= 10:
            stage = "Expanding"
        else:
            stage = "Mature"
        acc, rs3 = e["median_acceleration"], e["etf"]["rs_3m"]
        signal = "Accelerating" if (acc or 0) > 2 and (rs3 or 0) > 0 else "Slowing" if (acc or 0) < -5 or (rs3 or 0) < -5 else "Steady"
        ms = sizes.get(ind["id"])
        out.append({"id": ind["id"], "name": ind["name"], "companies": cs, "evidence": ev, "stage": stage, "signal": signal,
                    "drivers": ind["drivers"], "market_size": ms if (ms and ms.get("url")) else None})
    # scoring
    col = lambda f: [f(x) for x in out]
    p_yoy = _pctile(col(lambda x: x["evidence"]["median_rev_ttm_yoy"]))
    p_c3 = _pctile(col(lambda x: x["evidence"]["median_rev_cagr_3y"]))
    p_acc = _pctile(col(lambda x: x["evidence"]["median_acceleration"]))
    p_rs = _pctile(col(lambda x: x["evidence"]["etf"]["rs_6m"]))
    pe_ok = lambda x: x["evidence"]["median_fwd_pe"] and x["evidence"]["pe_coverage"] >= 0.5
    p_pe = _pctile(col(lambda x: x["evidence"]["median_fwd_pe"] if pe_ok(x) else None))
    gadj = col(lambda x: x["evidence"]["median_fwd_pe"] / max(x["evidence"]["median_rev_ttm_yoy"] or 1, 1) if pe_ok(x) else None)
    p_gadj = _pctile(gadj)
    p_ps = _pctile(col(lambda x: x["evidence"]["median_ps"]))
    for i, x in enumerate(out):
        if not pe_ok(x):
            p_pe[i] = p_gadj[i] = p_ps[i]
            x["evidence"]["pe_not_meaningful"] = True
    p_vol = _pctile(col(lambda x: x["evidence"]["etf"]["vol_1y"]))
    p_dd = _pctile(col(lambda x: abs(x["evidence"]["etf"]["max_dd_3y"]) if x["evidence"]["etf"]["max_dd_3y"] is not None else None))
    p_prof = _pctile(col(lambda x: x["evidence"]["pct_profitable"]))
    for i, x in enumerate(out):
        g = 0.35 * p_yoy[i] + 0.25 * p_c3[i] + 0.20 * p_acc[i] + 0.20 * p_rs[i]
        v = 0.4 * (100 - p_pe[i]) + 0.3 * (100 - p_gadj[i]) + 0.3 * (100 - p_ps[i])
        r = 0.5 * p_vol[i] + 0.3 * p_dd[i] + 0.2 * (100 - p_prof[i])
        x["scores"] = {"growth": g, "valuation": v, "risk": r, "composite": 0.5 * g + 0.3 * v + 0.2 * (100 - r),
                       "growth_adj_pe": gadj[i],
                       "components": {"p_ttm_yoy": p_yoy[i], "p_cagr3": p_c3[i], "p_accel": p_acc[i], "p_rs6m": p_rs[i], "p_fwd_pe": p_pe[i],
                                      "p_gadj_pe": p_gadj[i], "p_ps": p_ps[i], "p_vol": p_vol[i], "p_dd": p_dd[i], "p_profitable": p_prof[i]}}
    out.sort(key=lambda x: -x["scores"]["composite"])
    for n, x in enumerate(out, 1):
        x["rank"] = n
    return {"industries": out, "formula": FORMULA, "computed_at": iso(time.time())}


async def warm():
    await get_scanner()
    await radar()


@router.get("")
async def get_scanner():
    val, ts, _, stale = await cache.cached("scanner:v2", TTL_SCANNER, _compute)
    val["meta"] = M("SEC EDGAR XBRL (revenue, margins) + Yahoo Finance (ETF prices, forward P/E)", "https://www.sec.gov/edgar/sec-api-documentation",
                    ts, kind="derived", stale=stale, note="Rankings are evidence-weighted model outputs, not recommendations. Company lists per industry are MarketVision editorial selections.")
    return val


@router.get("/radar")
async def radar():
    async def compute():
        syms = [s for s, _ in RADAR] + ["SPY"]
        ch = await gather_limited([yahoo.chart(s, "2y", "1d") for s in syms], 8)
        perf = {s: yahoo.perf_from_rows(c["data"]["rows"]) for s, c in zip(syms, ch) if not isinstance(c, Exception)}
        spy = perf.get("SPY", {})
        rows = []
        for s, n in RADAR:
            p = perf.get(s)
            if not p:
                rows.append({"symbol": s, "name": n, "error": "data unavailable"})
                continue
            rs3 = (p["3m"] or 0) - (spy.get("3m") or 0)
            rs12 = (p["1y"] or 0) - (spy.get("1y") or 0)
            accel = rs3 * 4 - rs12  # annualized 3-mo RS vs 12-mo RS (rough)
            rows.append({"symbol": s, "name": n, "1m": p["1m"], "3m": p["3m"], "6m": p["6m"], "1y": p["1y"], "rs_3m": rs3, "rs_1y": rs12,
                         "rs_accel": accel, "above200": p["above200"], "vol_1y": p.get("vol_1y"),
                         "emerging": bool(rs3 > 0 and accel > 0 and p["above200"])})
        rows.sort(key=lambda r: -(r.get("rs_accel") or -1e9))
        return {"items": rows}
    val, ts, _, stale = await cache.cached("radar:v1", 3600, compute)
    val["rule"] = "Emerging-momentum flag: 3-mo return beats SPY, annualized 3-mo relative strength exceeds 12-mo relative strength (acceleration = 4×RS3m − RS12m), and price is above its 200-day average. Price momentum only — confirm with fundamentals."
    val["meta"] = M(yahoo.SOURCE, "https://finance.yahoo.com/etfs", ts, delayed="End-of-day", stale=stale, kind="derived")
    return val
