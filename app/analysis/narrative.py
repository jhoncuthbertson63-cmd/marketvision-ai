"""Rule-based, data-grounded narrative. Every sentence is generated from a number in the report and
tagged with its evidence type: fact (reported), derived (arithmetic on reported), estimate (analyst
consensus), model (MarketVision formula), editorial (qualitative interpretation)."""


_CUR = ["USD"]


def money(v):
    if v is None:
        return "n/a"
    a = abs(v)
    s = ("-" if v < 0 else "") + ("$" if _CUR[0] == "USD" else _CUR[0] + " ")
    if a >= 1e12:
        return f"{s}{a/1e12:.2f}T"
    if a >= 1e9:
        return f"{s}{a/1e9:.2f}B"
    if a >= 1e6:
        return f"{s}{a/1e6:.1f}M"
    return f"{s}{a:,.0f}"


def pct(v, d=1):
    return "n/a" if v is None else f"{v:.{d}f}%"


def S(text, kind="derived", short=None):
    d = {"text": text, "kind": kind}
    if short:
        d["short"] = short
    return d


def build(r: dict) -> dict:
    name = r.get("name") or r["ticker"]
    F = r.get("fundamentals") or {}
    rows = F.get("rows") or []
    G = F.get("growth") or {}
    T = F.get("ttm") or {}
    B = F.get("balance") or {}
    C = F.get("capital") or {}
    Q = r.get("quote") or {}
    V = r.get("valuation") or {}
    A = r.get("analyst") or {}
    SC = r.get("scenarios") or {}
    P = r.get("profile") or {}
    out = {}
    _CUR[0] = F.get("currency", "USD") if F else "USD"

    # --- what it does
    biz = []
    if P.get("summary"):
        first = P["summary"].split(". ")
        biz.append(S(". ".join(first[:3]).rstrip(".") + ".", "fact"))
    if P.get("sector") or P.get("sic_desc"):
        biz.append(S(f"Classified as {P.get('sector') or '—'} / {P.get('industry') or '—'} (Yahoo) and SIC '{P.get('sic_desc') or '—'}' (SEC).", "fact"))
    if T.get("revenue"):
        gm = T.get("gross_margin")
        biz.append(S(f"It generated {money(T['revenue'])} of revenue over the trailing twelve months"
                     + (f", keeping about {gm:.0f}¢ of gross profit per $1 of sales" if gm is not None else "") + ".", "derived"))
    biz.append(S("Segment-level revenue mix is not in the SEC XBRL summary API; see the segment note in the latest 10-K linked below.", "editorial"))
    out["business"] = biz

    # --- fundamentals
    fu = []
    if len(rows) >= 2 and rows[0].get("revenue") and rows[-1].get("revenue"):
        n = rows[-1]["fy"] - rows[0]["fy"]
        c = G.get(f"revenue_cagr_{10 if n >= 10 else 5 if n >= 5 else 3}y")
        fu.append(S(f"Revenue went from {money(rows[0]['revenue'])} (FY{rows[0]['fy']}) to {money(rows[-1]['revenue'])} (FY{rows[-1]['fy']})"
                    + (f", a {c:.1f}% compound annual rate" if c is not None else "") + ".", "derived"))
    if G.get("revenue_ttm_yoy") is not None:
        y = G["revenue_ttm_yoy"]
        c3 = G.get("revenue_cagr_3y")
        trend = ""
        if c3 is not None:
            trend = " — faster than its 3-year average, i.e. accelerating" if y > c3 + 2 else " — slower than its 3-year average, i.e. decelerating" if y < c3 - 2 else " — roughly in line with its 3-year average"
        fu.append(S(f"Trailing-twelve-month revenue is up {y:.1f}% year over year{trend} ({pct(c3)} 3-yr CAGR).", "derived"))
    nm, om, fm = T.get("net_margin"), T.get("operating_margin"), T.get("fcf_margin")
    if nm is not None:
        fu.append(S(f"TTM margins: operating {pct(om)}, net {pct(nm)}, free-cash-flow {pct(fm)}.", "derived"))
    if len(rows) >= 4 and rows[-1].get("net_margin") is not None and rows[-4].get("net_margin") is not None:
        d = rows[-1]["net_margin"] - rows[-4]["net_margin"]
        fu.append(S(f"Net margin {'expanded' if d > 0 else 'contracted'} by {abs(d):.1f} points over the last three fiscal years.", "derived"))
    if T.get("fcf") is not None:
        fu.append(S(f"Operating cash flow of {money(T.get('ocf'))} minus capex of {money(T.get('capex'))} = free cash flow of {money(T['fcf'])} (TTM).", "derived"))
    if B.get("total_debt") is not None:
        nd = B.get("net_debt")
        fu.append(S(f"Balance sheet ({B.get('as_of')}): {money(B.get('cash_and_st_investments'))} cash & short-term investments vs {money(B['total_debt'])} debt → "
                    + (f"net cash of {money(-nd)}." if nd is not None and nd < 0 else f"net debt of {money(nd)}."), "derived"))
    elif B.get("cash_and_st_investments") is not None:
        fu.append(S(f"Cash & short-term investments: {money(B['cash_and_st_investments'])}. Debt: {B.get('debt_method') or 'not reported in a standard tag'}.", "fact"))
    if B.get("roe_ttm") is not None:
        fu.append(S(f"Return on equity (TTM net income / average equity): {pct(B['roe_ttm'])}.", "derived"))
    out["fundamentals"] = fu

    # --- valuation
    va = []
    pe, fpe = Q.get("trailingPE"), Q.get("forwardPE")
    med = V.get("peer_median") or {}
    px = Q.get("regularMarketPrice")
    if pe:
        va.append(S(f"At ${px:,.2f} the stock trades at {pe:.1f}× trailing earnings"
                    + (f" and {fpe:.1f}× forward (analyst-estimated) earnings" if fpe and fpe > 0 else "") + ".", "derived"))
    elif px:
        va.append(S(f"At ${px:,.2f}, trailing P/E is not meaningful (no positive trailing earnings).", "derived"))
    if V.get("self", {}).get("ps") is not None:
        va.append(S(f"Price/Sales {V['self']['ps']:.1f}× and FCF yield {pct(V['self'].get('fcf_yield'))}.", "derived"))
    if med.get("fwd_pe") and fpe and fpe > 0:
        prem = (fpe / med["fwd_pe"] - 1) * 100
        va.append(S(f"Forward P/E is {abs(prem):.0f}% {'above' if prem > 0 else 'below'} the peer median of {med['fwd_pe']:.1f}× ({', '.join(V.get('peer_symbols', [])[:6])}).", "derived"))
    if med.get("ps") and V.get("self", {}).get("ps"):
        prem = (V["self"]["ps"] / med["ps"] - 1) * 100
        va.append(S(f"Price/Sales is {abs(prem):.0f}% {'above' if prem > 0 else 'below'} the peer median ({med['ps']:.1f}×).", "derived"))
    out["valuation"] = va

    # --- management & capital allocation
    ca = []
    if C.get("share_count_cagr_5y") is not None:
        s = C["share_count_cagr_5y"]
        ca.append(S(f"Diluted share count changed {s:+.2f}%/yr over ~5 years ({'net buybacks shrinking the share base' if s < -0.3 else 'net dilution' if s > 0.3 else 'roughly flat'}).", "derived"))
    if C.get("fcf_5y"):
        ca.append(S(f"Over the last 5 fiscal years: FCF {money(C['fcf_5y'])}, buybacks {money(C.get('buybacks_5y'))}, dividends {money(C.get('dividends_5y'))}"
                    + (f" — {pct(C.get('shareholder_return_pct_of_fcf'), 0)} of FCF returned to shareholders." if C.get('shareholder_return_pct_of_fcf') is not None else "."), "derived"))
    if rows and rows[-1].get("sbc_pct") is not None:
        ca.append(S(f"Stock-based compensation was {pct(rows[-1]['sbc_pct'])} of revenue in FY{rows[-1]['fy']}.", "derived"))
    if rows and rows[-1].get("rnd_pct") is not None:
        ca.append(S(f"R&D intensity: {pct(rows[-1]['rnd_pct'])} of revenue (FY{rows[-1]['fy']}).", "derived"))
    ca.append(S("Management quality is assessed here only through measurable outcomes (returns on capital, dilution, cash deployment). Executive track record & incentives: see the proxy statement (DEF 14A).", "editorial"))
    out["management"] = ca

    # --- advantages / risks (rule-based indicators)
    adv, risk = [], []
    gm = T.get("gross_margin")
    if gm is not None and gm > 60:
        adv.append(S(f"Gross margin of {gm:.0f}% is consistent with pricing power or differentiated products (an indicator, not proof, of a moat).", "editorial", "high gross margin / pricing power"))
    if B.get("roe_ttm") and B["roe_ttm"] > 20:
        adv.append(S(f"High return on equity ({B['roe_ttm']:.0f}%) suggests capital-efficient operations.", "editorial", "high return on equity"))
    if G.get("revenue_cagr_5y") and G["revenue_cagr_5y"] > 15:
        adv.append(S(f"Sustained revenue growth ({G['revenue_cagr_5y']:.0f}%/yr over 5 years) indicates strong demand for its offerings.", "editorial", "sustained multi-year revenue growth"))
    if B.get("net_debt") is not None and B["net_debt"] < 0:
        adv.append(S("Net cash balance sheet provides flexibility through downturns.", "derived", "net-cash balance sheet"))
    if fm is not None and fm > 20:
        adv.append(S(f"Strong cash conversion: {fm:.0f}% of revenue becomes free cash flow.", "derived", "strong free-cash-flow conversion"))
    if pe and pe > 40:
        risk.append(S(f"Valuation risk: {pe:.0f}× trailing earnings leaves little room for disappointment; multiples can compress even if the business grows.", "editorial", "rich earnings multiple"))
    if (V.get("self") or {}).get("ps") and V["self"]["ps"] > 15:
        risk.append(S(f"Price/Sales of {V['self']['ps']:.0f}× prices in many years of high growth.", "editorial", "high price/sales multiple"))
    if G.get("revenue_ttm_yoy") is not None and G.get("revenue_cagr_3y") is not None and G["revenue_ttm_yoy"] < G["revenue_cagr_3y"] - 5:
        risk.append(S("Growth is decelerating versus its 3-year trend.", "derived", "decelerating growth"))
    if nm is not None and nm < 0:
        risk.append(S(f"Unprofitable on a net basis (TTM net margin {nm:.1f}%); depends on reaching profitability or continued funding.", "derived", "not yet profitable"))
    if T.get("fcf") is not None and T["fcf"] < 0:
        risk.append(S("Negative free cash flow — the business consumes cash.", "derived", "cash burn"))
    if B.get("debt_to_equity") and B["debt_to_equity"] > 1.5:
        risk.append(S(f"Leverage: debt/equity of {B['debt_to_equity']:.1f}×.", "derived", "high leverage"))
    if C.get("share_count_cagr_5y") and C["share_count_cagr_5y"] > 3:
        risk.append(S(f"Shareholder dilution of {C['share_count_cagr_5y']:.1f}%/yr.", "derived", "ongoing shareholder dilution"))
    vol = (r.get("price_perf") or {}).get("vol_1y")
    if vol and vol > 45:
        risk.append(S(f"High price volatility ({vol:.0f}% annualized) — expect large drawdowns.", "derived", "high volatility"))
    risk.append(S("Company-specific risk factors (customer concentration, regulation, supply chain, competition) are disclosed in Item 1A of the 10-K linked below.", "editorial"))
    out["advantages"] = adv or [S("No rule-based advantage indicators triggered on the available data.", "editorial")]
    out["risks"] = risk

    # --- growth outlook
    go = []
    if A.get("revenue_growth_current_fy") is not None:
        go.append(S(f"Analysts expect revenue growth of {pct(A['revenue_growth_current_fy'])} this fiscal year and {pct(A.get('revenue_growth_next_fy'))} next ({A.get('revenue_analysts') or '?'} analysts).", "estimate"))
    if A.get("eps_growth_next_fy") is not None:
        go.append(S(f"Consensus EPS growth next fiscal year: {pct(A['eps_growth_next_fy'])}.", "estimate"))
    if SC.get("available"):
        b = SC["scenarios"]["base"]["result"]["path"]
        go.append(S(f"MarketVision base model fades growth from {b[0]['growth']*100:.1f}% to {b[-1]['growth']*100:.1f}% by year 5, implying ~{money(b[2]['revenue'])} revenue in year 3 and ~{money(b[-1]['revenue'])} in year 5.", "model"))
    out["growth"] = go

    # --- conclusion
    con = []
    if SC.get("available"):
        s = SC["scenarios"]
        f = lambda k: s[k]["result"]["annual_return"]
        con.append(S(f"Under transparent assumptions, the 5-year model gives roughly {f('bear')*100:+.0f}%/yr (bear), {f('base')*100:+.0f}%/yr (base) and {f('bull')*100:+.0f}%/yr (bull) price returns. These are formula outputs, not predictions.", "model"))
        con.append(S(SC["required"]["explain"] + (" That is above the analyst next-year growth estimate." if A.get("revenue_growth_next_fy") is not None and SC["required"]["required_revenue_cagr"] * 100 > A["revenue_growth_next_fy"] else ""), "model"))
    pos = [x["short"] for x in adv if x.get("short")]
    neg = [x["short"] for x in risk if x.get("short")]
    con.append(S("What looks attractive (rule-based): " + (", ".join(pos) if pos else "no rule-based positives triggered") + ".", "editorial"))
    con.append(S("What looks unattractive / biggest risks (rule-based): " + (", ".join(neg) if neg else "no rule-based red flags triggered — still review 10-K risk factors") + ".", "editorial"))
    con.append(S("Thesis check: watch whether reported revenue growth and margins track the base case each quarter; a sustained miss versus the required growth rate would weaken the thesis.", "editorial"))
    out["conclusion"] = con
    return out
