"""Transparent, formula-driven bull/base/bear projections. These are MODEL FORECASTS from stated
assumptions, not predictions. The identical formula is implemented client-side for the simulator."""

FORMULA = {
    "growth_path": "g_t = g_start + (g_terminal - g_start) * (t-1)/(N-1)  for t = 1..N  (linear fade)",
    "revenue": "Revenue_N = Revenue_TTM * Π(1 + g_t)",
    "earnings": "NetIncome_N = Revenue_N * NetMargin_N        (P/E method)",
    "shares": "Shares_N = Shares_0 * (1 + share_change)^N",
    "price_pe": "Price_N = NetIncome_N * ExitPE / Shares_N",
    "price_ps": "Price_N = Revenue_N * ExitPS / Shares_N        (P/S method, used when margins are thin/negative)",
    "return": "Implied annual return = (Price_N / Price_0)^(1/N) - 1   (excludes dividends)",
}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def project(a: dict) -> dict:
    """a: revenue0, shares0, price0, years, g_start, g_terminal, margin (fraction), exit_multiple, method, share_change"""
    N = int(a["years"])
    rev = a["revenue0"]
    path = []
    for t in range(1, N + 1):
        g = a["g_start"] + (a["g_terminal"] - a["g_start"]) * ((t - 1) / (N - 1) if N > 1 else 1)
        rev *= (1 + g)
        path.append({"year": t, "growth": g, "revenue": rev})
    shares = a["shares0"] * (1 + a["share_change"]) ** N
    if a["method"] == "pe":
        ni = rev * a["margin"]
        price = ni * a["exit_multiple"] / shares
    else:
        ni = rev * a["margin"]
        price = rev * a["exit_multiple"] / shares
    ret = (price / a["price0"]) ** (1 / N) - 1 if price > 0 and a["price0"] else None
    return {"path": path, "revenue_n": rev, "net_income_n": ni, "shares_n": shares, "price_n": price,
            "annual_return": ret, "total_return": price / a["price0"] - 1 if a["price0"] else None}


def build(fund: dict, quote: dict, analyst: dict) -> dict:
    ttm = fund["ttm"]
    rev0 = ttm.get("revenue")
    price0 = quote.get("regularMarketPrice")
    # implied total shares = market cap / price (handles multi-class companies consistently)
    shares0 = (quote["marketCap"] / price0 if quote.get("marketCap") and price0 else None) or quote.get("sharesOutstanding") or (fund.get("shares_outstanding") or {}).get("val")
    if not shares0 and fund["rows"]:
        shares0 = fund["rows"][-1].get("diluted_shares")
    if rev0 is not None and rev0 <= 0 and price0 and shares0:
        return {"available": False, "pre_revenue": True,
                "reason": f"Not applicable: SEC filings show no revenue over the trailing 12 months (TTM to {ttm.get('end')}). "
                          "A revenue-and-margin scenario model would be meaningless for a pre-revenue company; its value depends on "
                          "events such as trial results, approvals or financing, which this model does not forecast."}
    if not (rev0 and price0 and shares0):
        missing = [n for n, v in (("TTM revenue (SEC)", rev0), ("price (Yahoo)", price0), ("share count", shares0)) if not v]
        return {"available": False, "reason": "Needs TTM revenue (SEC), price and share count (Yahoo) — missing: " + ", ".join(missing) + "."}
    notes = []
    # starting growth
    g_an = analyst.get("revenue_growth_next_fy")
    g_hist = fund["growth"].get("revenue_cagr_3y")
    if g_an is not None:
        g_start = g_an / 100
        notes.append(f"Base starting growth = analyst consensus revenue growth for next fiscal year ({g_an:.1f}%, Yahoo Finance).")
    elif g_hist is not None:
        g_start = g_hist / 100
        notes.append(f"Base starting growth = 3-year historical revenue CAGR ({g_hist:.1f}%, SEC filings) — no analyst estimate available.")
    else:
        g_start = 0.05
        notes.append("Base starting growth defaulted to 5% (no analyst estimate or 3-year history available).")
    g_raw = g_start
    g_start = clamp(g_start, -0.20, 0.60)
    if g_start != g_raw:
        notes.append(f"Starting growth clamped from {g_raw*100:.1f}% to {g_start*100:.1f}% (model bounds −20%…+60% to avoid extrapolating extreme single-year growth).")
    nm = ttm.get("net_margin")
    rows = fund["rows"]
    hist_nm = [r["net_margin"] for r in rows[-3:] if r.get("net_margin") is not None]
    method = "pe" if (nm is not None and nm > 3) else "ps"
    mcap = quote.get("marketCap") or price0 * shares0
    if method == "pe":
        base_margin = nm / 100
        pe_now = quote.get("trailingPE") or (mcap / ttm["net_income"] if ttm.get("net_income") else None)
        base_mult = clamp(((pe_now or 20) + 20) / 2, 10, 45)
        notes.append(f"Valuation method: P/E (TTM net margin {nm:.1f}% > 3%). Base exit P/E = average of current P/E "
                     f"({pe_now:.1f}x) and a 20x market-like multiple, clamped to 10–45x → {base_mult:.1f}x." if pe_now else
                     f"Base exit P/E = 20x (current P/E unavailable).")
        notes.append(f"Base net margin held at TTM level ({nm:.1f}%).")
        cur_mult = pe_now
    else:
        ps_now = mcap / rev0
        base_mult = clamp((ps_now + 3) / 2, 0.5, 20)
        base_margin = (nm or 0) / 100
        notes.append(f"Valuation method: Price/Sales (TTM net margin {nm if nm is not None else float('nan'):.1f}% ≤ 3%, so P/E is not meaningful). "
                     f"Base exit P/S = average of current P/S ({ps_now:.2f}x) and 3x, clamped 0.5–20x → {base_mult:.2f}x.")
        cur_mult = ps_now
    sc = fund["capital"].get("share_count_cagr_5y")
    share_change = clamp((sc or 0) / 100, -0.04, 0.08)
    notes.append(f"Share count change per year = historical 5-year diluted share CAGR ({(sc or 0):.2f}%), clamped −4%…+8%.")
    years = 5
    spread_up = max(0.05, 0.25 * abs(g_start))
    spread_dn = max(0.07, 0.40 * abs(g_start))
    sc_defs = {
        "bull": dict(g_start=g_start + spread_up, g_terminal=0.08, margin=min(base_margin + 0.03, 0.6) if method == "pe" else base_margin,
                     exit_multiple=base_mult * 1.25),
        "base": dict(g_start=g_start, g_terminal=0.05, margin=base_margin, exit_multiple=base_mult),
        "bear": dict(g_start=g_start - spread_dn, g_terminal=0.02, margin=max(base_margin - 0.05, base_margin * 0.7) if method == "pe" else base_margin,
                     exit_multiple=base_mult * 0.70),
    }
    out = {}
    for name, d in sc_defs.items():
        a = dict(revenue0=rev0, shares0=shares0, price0=price0, years=years, method=method, share_change=share_change, **d)
        out[name] = {"assumptions": a, "result": project(a)}
    # what must happen: revenue CAGR required for 8%/yr with base margin & multiple
    target = price0 * 1.08 ** years
    shares_n = shares0 * (1 + share_change) ** years
    if method == "pe" and base_margin > 0:
        rev_req = target * shares_n / (base_margin * base_mult)
    else:
        rev_req = target * shares_n / base_mult
    req_cagr = (rev_req / rev0) ** (1 / years) - 1
    return {"available": True, "method": method, "current_multiple": cur_mult, "scenarios": out, "notes": notes,
            "formula": FORMULA, "spread_rule": "Bull start growth = base + max(5pp, 25% of |base|); bear = base − max(7pp, 40% of |base|). "
            "Terminal growth: bull 8%, base 5%, bear 2%. Bull multiple = base × 1.25, bear = base × 0.70. "
            "Bull margin = base + 3pp; bear margin = max(base − 5pp, base × 0.7) (P/E method only).",
            "required": {"target_annual_return": 0.08, "required_revenue_cagr": req_cagr, "required_revenue_n": rev_req,
                         "explain": f"For an 8%/yr price return over {years} years at the base-case margin and exit multiple, "
                                    f"revenue would need to compound at about {req_cagr*100:.1f}%/yr."},
            "kind": "model_forecast"}
