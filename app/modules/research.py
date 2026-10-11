import asyncio, datetime as dt, re, statistics
from fastapi import APIRouter, HTTPException
from ..providers import yahoo, sec
from ..analysis import fundamentals as fundmod, scenarios as scmod, narrative
from ..analysis.universe import industry_peers
from ..core import llm
from .common import M, iso, delay_label, gather_limited

router = APIRouter(prefix="/api", tags=["research"])
R = yahoo.raw
ITEMS_8K = {"1.01": "Material agreement", "1.02": "Agreement terminated", "1.05": "Cybersecurity incident", "2.01": "Acquisition/disposition completed",
            "2.02": "Earnings results", "2.03": "New debt obligation", "2.05": "Restructuring costs", "2.06": "Impairment",
            "3.02": "Unregistered equity sale", "5.02": "Executive/director change", "5.07": "Shareholder vote results",
            "7.01": "Reg FD disclosure", "8.01": "Other material event", "9.01": "Financial exhibits", "5.03": "Bylaw change",
            "1.03": "Bankruptcy", "4.02": "Non-reliance on prior financials", "3.01": "Delisting notice"}


@router.get("/search")
async def search(q: str):
    q = q.strip().upper()
    m = await sec.ticker_map()
    hits = [{"symbol": t, "name": v["name"]} for t, v in m.items() if t.startswith(q)][:8]
    if len(hits) < 8 and len(q) >= 2:
        hits += [{"symbol": t, "name": v["name"]} for t, v in m.items() if q in v["name"].upper() and not t.startswith(q)][:8 - len(hits)]
    hits.sort(key=lambda h: (h["symbol"] != q, len(h["symbol"])))
    return {"results": hits}


def _analyst(summ: dict) -> dict:
    out = {}
    trend = {t["period"]: t for t in (summ.get("earningsTrend") or {}).get("trend", [])}
    for per, lab in (("0q", "current_q"), ("+1q", "next_q"), ("0y", "current_fy"), ("+1y", "next_fy")):
        t = trend.get(per)
        if not t:
            continue
        g = R((t.get("revenueEstimate") or {}).get("growth"))
        out[f"revenue_growth_{lab}"] = g * 100 if g is not None else None
        out[f"revenue_est_{lab}"] = R((t.get("revenueEstimate") or {}).get("avg"))
        e = R((t.get("earningsEstimate") or {}).get("growth"))
        out[f"eps_growth_{lab}"] = e * 100 if e is not None else None
        out[f"eps_est_{lab}"] = R((t.get("earningsEstimate") or {}).get("avg"))
        out[f"period_end_{lab}"] = t.get("endDate")
        if lab == "next_fy":
            out["revenue_analysts"] = R((t.get("revenueEstimate") or {}).get("numberOfAnalysts"))
    if "+5y" in trend and R(trend["+5y"].get("growth")) is not None:
        out["eps_growth_5y_pa"] = R(trend["+5y"]["growth"]) * 100
    fd = summ.get("financialData") or {}
    out["targets"] = {k: R(fd.get(k)) for k in ("targetLowPrice", "targetMeanPrice", "targetMedianPrice", "targetHighPrice", "numberOfAnalystOpinions")}
    out["recommendation"] = fd.get("recommendationKey")
    rt = (summ.get("recommendationTrend") or {}).get("trend") or []
    out["rec_trend"] = rt[:4]
    eh = (summ.get("earningsHistory") or {}).get("history") or []
    out["surprises"] = [{"quarter": (h.get("quarter") or {}).get("fmt"), "actual": R(h.get("epsActual")), "estimate": R(h.get("epsEstimate")),
                         "surprise_pct": (R(h.get("surprisePercent")) or 0) * 100 if R(h.get("surprisePercent")) is not None else None} for h in eh]
    ce = (summ.get("calendarEvents") or {}).get("earnings") or {}
    ed = ce.get("earningsDate") or []
    out["next_earnings"] = {"date": ed[0].get("fmt") if ed else None, "is_estimate": ce.get("isEarningsDateEstimate"),
                            "eps_avg": R(ce.get("earningsAverage")), "revenue_avg": R(ce.get("revenueAverage"))}
    return out


async def _peer_metrics(sym):
    info = await sec.lookup(sym)
    rev = growth = None
    if info:
        try:
            f = (await sec.facts(info["cik"]))["data"]
            fb = fundmod.build(f)
            if fb["currency"] != "USD":
                return {"symbol": sym, "revenue_ttm": None, "revenue_ttm_yoy": fb["growth"].get("revenue_ttm_yoy")}
            rev, growth = fb["ttm"].get("revenue"), fb["growth"].get("revenue_ttm_yoy")
        except Exception:
            pass
    return {"symbol": sym, "revenue_ttm": rev, "revenue_ttm_yoy": growth}


@router.get("/research/{ticker}")
async def research(ticker: str, narrative_mode: str = "auto"):
    t = ticker.upper().strip()
    if not re.fullmatch(r"[A-Z0-9.\-^]{1,10}", t):
        raise HTTPException(400, "invalid ticker")
    gaps = []
    info = await sec.lookup(t)
    ysym = t.replace(".", "-")

    async def safe(coro, label):
        try:
            return await coro
        except Exception as e:
            msg = f"{label}: unavailable ({type(e).__name__})"
            if label == "SEC XBRL financials":
                msg = "SEC XBRL financials: none on file (ETFs, funds and some foreign issuers do not file company financial statements in XBRL)."
            gaps.append(msg)
            return None

    quote_r, summ_r, chart_r, news_r = await asyncio.gather(
        safe(yahoo.quotes([ysym]), "Yahoo quote"),
        safe(yahoo.summary(ysym, "assetProfile,financialData,earningsTrend,recommendationTrend,earningsHistory,calendarEvents,defaultKeyStatistics"), "Yahoo analyst/profile data"),
        safe(yahoo.chart(ysym, "10y", "1d"), "Price history"),
        safe(yahoo.search_news(ysym, 8), "News headlines"))
    facts_r = subs_r = None
    if info:
        facts_r, subs_r = await asyncio.gather(safe(sec.facts(info["cik"]), "SEC XBRL financials"), safe(sec.submissions(info["cik"]), "SEC filings"))
    else:
        gaps.append("Not found in SEC EDGAR ticker list (foreign/OTC/ETF?) — fundamentals from filings unavailable.")
    q = (quote_r or {}).get("data", {}).get(ysym) if quote_r else None
    if not q and not facts_r:
        raise HTTPException(404, f"No data found for {t}")
    summ = (summ_r or {}).get("data") or {}
    ap = summ.get("assetProfile") or {}
    sd = (subs_r or {}).get("data") or {}
    profile = {"summary": ap.get("longBusinessSummary"), "sector": ap.get("sector"), "industry": ap.get("industry"),
               "employees": ap.get("fullTimeEmployees"), "website": ap.get("website"), "country": ap.get("country"),
               "officers": [{"name": o.get("name"), "title": o.get("title"), "age": o.get("age")} for o in (ap.get("companyOfficers") or [])[:5]],
               "sic_desc": sd.get("sic_desc"), "fiscal_year_end": sd.get("fiscal_year_end"), "exchanges": sd.get("exchanges"),
               "meta": M("Yahoo Finance profile; SEC EDGAR submissions", f"https://finance.yahoo.com/quote/{ysym}/profile", (summ_r or {}).get("fetched_at"))}
    fund = None
    if facts_r:
        fund = fundmod.build(facts_r["data"])
        fund["meta"] = M("SEC EDGAR XBRL companyfacts (as-reported 10-K/10-Q)", facts_r["url"], facts_r["fetched_at"], stale=facts_r["stale"],
                         note="Annual = fiscal-year 10-K values (latest restatement). TTM = sum of last four quarters (Q4 derived as FY − Q1..Q3 where needed).")
        if fund["currency"] != "USD":
            gaps.append(f"SEC financials are reported in {fund['currency']} (not converted). USD-based valuation ratios, peer comparison and scenarios are disabled to avoid mixing currencies.")
        if not fund["rows"]:
            gaps.append("SEC XBRL has no standard revenue tag for this filer (IFRS/foreign or non-standard taxonomy).")
    analyst = _analyst(summ) if summ else {}
    if analyst:
        analyst["meta"] = M("Yahoo Finance analyst consensus", f"https://finance.yahoo.com/quote/{ysym}/analysis", summ_r["fetched_at"], kind="estimate",
                            note="Third-party analyst estimates and targets — not facts, and not MarketVision forecasts.")
    # price history & performance
    price_perf, hist = {}, []
    if chart_r:
        rows = chart_r["data"]["rows"]
        price_perf = yahoo.perf_from_rows(rows)
        hist = [[r[0] * 1000, round(r[1] or r[4], 4), round(r[2] or r[4], 4), round(r[3] or r[4], 4), round(r[4], 4), r[5]] for r in rows]
    quote = {}
    if q:
        quote = {k: q.get(k) for k in ("regularMarketPrice", "regularMarketChange", "regularMarketChangePercent", "marketCap", "trailingPE", "forwardPE",
                                       "priceToBook", "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "regularMarketVolume", "averageDailyVolume3Month",
                                       "sharesOutstanding", "epsTrailingTwelveMonths", "epsForward", "dividendYield", "currency", "fullExchangeName",
                                       "longName", "shortName", "marketState", "regularMarketTime", "quoteType", "averageAnalystRating")}
        quote["meta"] = M(yahoo.SOURCE, f"https://finance.yahoo.com/quote/{ysym}", quote_r["fetched_at"], delayed=delay_label(q), as_of=iso(q.get("regularMarketTime")))
    else:
        gaps.append("Live/delayed quote unavailable — valuation multiples and scenarios that need price are disabled.")
    name = (q or {}).get("longName") or (info or {}).get("name") or t

    # valuation vs peers
    valuation = {}
    if q and fund and fund["currency"] == "USD":
        mcap = q.get("marketCap")
        T, B = fund["ttm"], fund["balance"]
        ev = mcap + (B.get("total_debt") or 0) - (B.get("cash_and_st_investments") or 0) if mcap else None
        valuation["self"] = {"pe": q.get("trailingPE"), "fwd_pe": q.get("forwardPE"), "pb": q.get("priceToBook"),
                             "ps": mcap / T["revenue"] if mcap and T.get("revenue") else None,
                             "ev": ev, "ev_sales": ev / T["revenue"] if ev and T.get("revenue") else None,
                             "p_fcf": mcap / T["fcf"] if mcap and T.get("fcf") and T["fcf"] > 0 else None,
                             "fcf_yield": T["fcf"] / mcap * 100 if mcap and T.get("fcf") is not None else None}
        curated, groups = industry_peers(t)
        ypeers = await yahoo.peers(ysym)
        cand = (curated + [p for p in ypeers if p not in curated])[:7]
        valuation["peer_source"] = ("MarketVision industry group: " + ", ".join(groups)) if curated else "Yahoo Finance 'similar symbols' (may include non-competitors)"
        if cand:
            try:
                pq = (await yahoo.quotes(cand))["data"]
            except Exception:
                pq = {}
            cand = [c for c in cand if pq.get(c, {}).get("quoteType") == "EQUITY"][:6]
            pm = await gather_limited([_peer_metrics(c) for c in cand], 4)
            peers = []
            for c, m in zip(cand, pm):
                qq = pq[c]
                mrev = m if not isinstance(m, Exception) else {}
                mc = qq.get("marketCap")
                peers.append({"symbol": c, "name": qq.get("shortName"), "price": qq.get("regularMarketPrice"), "market_cap": mc,
                              "pe": qq.get("trailingPE"), "fwd_pe": qq.get("forwardPE"), "pb": qq.get("priceToBook"),
                              "ps": mc / mrev["revenue_ttm"] if mc and mrev.get("revenue_ttm") else None,
                              "revenue_ttm_yoy": mrev.get("revenue_ttm_yoy"), "chg_52w": qq.get("fiftyTwoWeekChangePercent")})
            valuation["peers"] = peers
            valuation["peer_symbols"] = [p["symbol"] for p in peers]

            def med(k):
                v = [p[k] for p in peers if p.get(k) is not None and p[k] > 0]
                return statistics.median(v) if v else None
            valuation["peer_median"] = {k: med(k) for k in ("pe", "fwd_pe", "pb", "ps", "revenue_ttm_yoy")}
        valuation["meta"] = M("Yahoo Finance (price, P/E) + SEC EDGAR (revenue, FCF, debt)", f"https://finance.yahoo.com/quote/{ysym}/key-statistics",
                              quote_r["fetched_at"], note="P/S, EV/Sales, P/FCF computed by MarketVision: market cap ÷ TTM figure from SEC filings. EV = market cap + debt − cash & ST investments.")
    if fund and q and fund["currency"] != "USD":
        scen = {"available": False, "reason": f"Financials are in {fund['currency']}; scenarios need USD-denominated revenue to match the USD share price."}
    else:
        scen = scmod.build(fund, q, analyst) if (fund and q) else {"available": False, "reason": "Needs SEC fundamentals and a quote."}

    # growth outlook 1/3/5y
    outlook = {}
    if analyst.get("revenue_growth_next_fy") is not None or analyst.get("revenue_growth_current_fy") is not None:
        outlook["y1"] = {"revenue_growth": analyst.get("revenue_growth_next_fy") if analyst.get("revenue_growth_next_fy") is not None else analyst.get("revenue_growth_current_fy"),
                         "eps_growth": analyst.get("eps_growth_next_fy"), "kind": "estimate", "source": "Analyst consensus via Yahoo Finance"}
    if scen.get("available"):
        p = scen["scenarios"]["base"]["result"]["path"]
        r0 = scen["scenarios"]["base"]["assumptions"]["revenue0"]
        outlook["y3"] = {"revenue_cagr": ((p[2]["revenue"] / r0) ** (1 / 3) - 1) * 100, "kind": "model", "source": "MarketVision base-case fade model"}
        outlook["y5"] = {"revenue_cagr": ((p[4]["revenue"] / r0) ** (1 / 5) - 1) * 100, "kind": "model", "source": "MarketVision base-case fade model"}
    if analyst.get("eps_growth_5y_pa") is not None:
        outlook["y5_analyst_eps"] = {"eps_growth": analyst["eps_growth_5y_pa"], "kind": "estimate", "source": "Analyst long-term EPS growth (Yahoo)"}

    # catalysts
    filings = sd.get("filings", [])
    k8 = []
    for f in filings:
        if f["form"] in ("8-K", "6-K") and len(k8) < 10:
            codes = [c.strip() for c in (f.get("items") or "").split(",") if c.strip()]
            k8.append({**f, "item_labels": [ITEMS_8K.get(c, f"Item {c}") for c in codes if c != "9.01"]})
    periodic = [f for f in filings if f["form"] in ("10-K", "10-Q", "20-F", "40-F")][:6]
    proxy = next((f for f in filings if f["form"] == "DEF 14A"), None)
    news = (news_r or {}).get("data", {}).get("news", []) if news_r else []
    catalysts = {"next_earnings": analyst.get("next_earnings"), "filings_8k": k8, "periodic": periodic, "proxy": proxy, "news": news,
                 "meta_filings": M("SEC EDGAR submissions", (subs_r or {}).get("url"), (subs_r or {}).get("fetched_at")),
                 "meta_news": M("Yahoo Finance news search (headlines link to original publishers)", f"https://finance.yahoo.com/quote/{ysym}/news",
                                (news_r or {}).get("fetched_at"), kind="news", note="Headlines are third-party reporting, not verified by MarketVision.")}
    report = {"ticker": t, "name": name, "cik": (info or {}).get("cik"), "profile": profile, "quote": quote, "price_history": hist,
              "price_perf": price_perf, "price_meta": M(chart_r.get("source", yahoo.SOURCE), chart_r.get("url"), chart_r["fetched_at"], delayed="End-of-day daily bars (split/dividend-adjusted close used for returns)") if chart_r else None,
              "fundamentals": fund, "analyst": analyst, "valuation": valuation, "scenarios": scen, "outlook": outlook,
              "catalysts": catalysts, "data_gaps": gaps, "generated_at": iso(dt.datetime.now().timestamp())}
    rb = narrative.build(report)
    report["narrative"] = {"mode": "rule_based", "label": "Rule-based summary generated from the reported numbers on this page (no LLM key configured).", "sections": rb}
    if llm.provider() and narrative_mode != "rule":
        compact = {"company": name, "ticker": t, "profile": {k: profile.get(k) for k in ("summary", "sector", "industry", "sic_desc")},
                   "annual_financials": fund["rows"][-6:] if fund else None, "ttm": fund and fund["ttm"], "balance": fund and fund["balance"],
                   "growth": fund and {k: v for k, v in fund["growth"].items() if k != "quarterly_revenue"}, "capital_allocation": fund and fund["capital"],
                   "valuation": {k: valuation.get(k) for k in ("self", "peer_median", "peer_symbols")}, "analyst_consensus": {k: v for k, v in analyst.items() if k != "meta"},
                   "scenario_results": scen.get("available") and {k: {"annual_return": v["result"]["annual_return"], "assumptions": v["assumptions"]} for k, v in scen["scenarios"].items()},
                   "recent_8k": [{"date": f["date"], "items": f["item_labels"]} for f in k8], "news_headlines": [n["title"] for n in news]}
        res = await llm.complete_json(
            "Write an investment research narrative for this company. Sections: business (what it does and how it makes money), fundamentals, valuation, "
            "management (capital allocation), advantages (competitive advantages), risks, growth (1/3/5 year outlook referencing analyst estimates vs model), "
            "conclusion (what makes it attractive/unattractive, biggest risks, what must happen for the thesis to succeed). Cite numbers from DATA only.",
            compact, ["business", "fundamentals", "valuation", "management", "advantages", "risks", "growth", "conclusion"])
        if res and "content" in res:
            secs = {k: [{"text": x, "kind": "ai"} for x in (v if isinstance(v, list) else [v])] for k, v in res["content"].items()}
            report["narrative"] = {"mode": "llm", "label": f"AI narrative by {res['provider']} ({res['model']}) generated only from the data on this page. AI can misread data — verify against the sourced tables.",
                                   "sections": secs, "rule_based": rb}
        elif res:
            report["narrative"]["llm_error"] = res.get("error")
    return report
