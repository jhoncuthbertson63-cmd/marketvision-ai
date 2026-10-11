"""Turns distilled EDGAR XBRL into a 10-year financial table + derived metrics. Every number here is
either reported (fact) or arithmetic on reported values (derived, formula recorded)."""
import datetime as dt


def _safe_div(a, b):
    try:
        if a is None or b in (None, 0):
            return None
        return a / b
    except Exception:
        return None


def cagr(first, last, years):
    if first is None or last is None or years <= 0 or first <= 0 or last <= 0:
        return None
    return ((last / first) ** (1 / years) - 1) * 100


def _latest(d: dict):
    if not d:
        return None, None
    k = max(d)
    return k, d[k]


SPLITS = [2, 3, 4, 5, 6, 8, 10, 15, 20, 25, 30, 40, 50]


def split_adjust(A: dict) -> list:
    """Old 10-K share counts/EPS are not restated for later stock splits. Detect year-over-year share-count
    jumps that match a common split ratio (within 8%) and restate earlier years. Returns notes."""
    sh = A.get("diluted_shares") or {}
    eps = A.get("eps_diluted") or {}
    ends = sorted(sh)
    notes = []
    for i in range(len(ends) - 1, 0, -1):
        a, b = sh[ends[i - 1]], sh[ends[i]]
        if not a or not b:
            continue
        ratio = b / a
        for k in SPLITS:
            if abs(ratio / k - 1) < 0.08:
                for e in ends[:i]:
                    sh[e] *= k
                for e in list(eps):
                    if e <= ends[i - 1]:
                        eps[e] /= k
                notes.append(f"{k}-for-1 split detected between FY{ends[i-1][:4]} and FY{ends[i][:4]}: earlier share counts and EPS restated.")
                break
    return notes


def build(f: dict) -> dict:
    import copy
    f = copy.deepcopy(f)
    A = f["annual"]
    split_notes = split_adjust(A)
    rev = A.get("revenue", {})
    years = sorted(rev)[-10:]
    rows = []
    for e in years:
        r = rev.get(e)
        g = lambda k: A.get(k, {}).get(e)
        prev = [y for y in sorted(rev) if y < e]
        pr = rev.get(prev[-1]) if prev else None
        ocf, capex = g("ocf"), g("capex")
        fcf = ocf - capex if ocf is not None and capex is not None else None
        gp = g("gross_profit")
        rows.append({
            "fy_end": e, "fy": int(e[:4]), "revenue": r, "revenue_yoy": (_safe_div(r, pr) - 1) * 100 if pr and r else None,
            "gross_profit": gp, "gross_margin": _pct(gp, r), "operating_income": g("operating_income"),
            "operating_margin": _pct(g("operating_income"), r), "net_income": g("net_income"),
            "net_margin": _pct(g("net_income"), r), "eps_diluted": g("eps_diluted"), "ocf": ocf, "capex": capex,
            "fcf": fcf, "fcf_margin": _pct(fcf, r), "rnd": g("rnd"), "rnd_pct": _pct(g("rnd"), r), "sbc": g("sbc"),
            "sbc_pct": _pct(g("sbc"), r), "buybacks": g("buybacks"), "dividends": g("dividends"),
            "diluted_shares": g("diluted_shares"),
        })
    T = f.get("ttm", {})
    tv = lambda k: (T.get(k) or {}).get("val")
    ttm = {"end": (T.get("revenue") or {}).get("end"), "method": (T.get("revenue") or {}).get("method"),
           "revenue": tv("revenue"), "net_income": tv("net_income"), "operating_income": tv("operating_income"),
           "gross_profit": tv("gross_profit"), "ocf": tv("ocf"), "capex": tv("capex"), "rnd": tv("rnd"), "sbc": tv("sbc"),
           "interest_expense": tv("interest_expense")}
    if ttm["gross_profit"] is None and tv("cost_of_revenue") is not None and ttm["revenue"]:
        ttm["gross_profit"] = ttm["revenue"] - tv("cost_of_revenue")
    ttm["fcf"] = ttm["ocf"] - ttm["capex"] if ttm["ocf"] is not None and ttm["capex"] is not None else None
    for k in ("gross_profit", "operating_income", "net_income", "fcf"):
        ttm[k.replace("_income", "").replace("gross_profit", "gross") + "_margin"] = _pct(ttm[k], ttm["revenue"])

    # balance sheet at latest instant
    I = f["instant"]
    d_cash, cash = _latest(I.get("cash", {}))
    d_sti, sti = _latest(I.get("st_investments", {}))
    if d_sti and d_cash and d_sti != d_cash:
        sti = I["st_investments"].get(d_cash)
    d_eq, equity = _latest(I.get("equity", {}))
    d_as, assets = _latest(I.get("assets", {}))
    debt, debt_method, d_debt = None, None, None
    cands = [d for d in [_latest(I.get("lt_debt_total", {}))[0], _latest(I.get("lt_debt_noncurrent", {}))[0]] if d]
    if cands:
        d_debt = max(cands)
        if d_debt in I.get("lt_debt_total", {}):
            debt = I["lt_debt_total"][d_debt]
            debt_method = "LongTermDebt (incl. current portion)"
        else:
            debt = I["lt_debt_noncurrent"][d_debt] + (I.get("debt_current", {}).get(d_debt) or 0)
            debt_method = "LongTermDebtNoncurrent + current portion"
        if d_as and (dt.date.fromisoformat(d_as) - dt.date.fromisoformat(d_debt)).days > 400:
            debt, debt_method = None, "not found in standard recent XBRL debt tags (banks/insurers and some filers use other tags) — see balance sheet in latest filing"
    liquid = (cash or 0) + (sti or 0) if cash is not None else None
    bal = {"as_of": d_cash or d_eq, "cash_and_st_investments": liquid, "total_debt": debt, "debt_method": debt_method,
           "debt_as_of": d_debt, "net_debt": (debt - liquid) if debt is not None and liquid is not None else None,
           "equity": equity, "assets": assets, "debt_to_equity": _safe_div(debt, equity) if equity and equity > 0 else None}
    eqs = sorted(I.get("equity", {}).items())
    if ttm["net_income"] is not None and len(eqs) >= 1:
        avg_eq = sum(v for _, v in eqs[-5:]) / len(eqs[-5:])
        bal["roe_ttm"] = _pct(ttm["net_income"], avg_eq) if avg_eq > 0 else None
    bal["interest_coverage"] = _safe_div(ttm["operating_income"], ttm["interest_expense"]) if ttm["interest_expense"] else None

    # growth
    def series(key):
        return [(r["fy"], r[key]) for r in rows if r.get(key) is not None]

    def c(key, n):
        s = series(key)
        if len(s) < n + 1:
            return None
        return cagr(s[-n - 1][1], s[-1][1], s[-1][0] - s[-n - 1][0])
    growth = {f"revenue_cagr_{n}y": c("revenue", n) for n in (3, 5, 10)}
    growth.update({f"net_income_cagr_{n}y": c("net_income", n) for n in (3, 5)})
    growth.update({f"eps_cagr_{n}y": c("eps_diluted", n) for n in (3, 5)})
    growth["revenue_yoy_latest_fy"] = rows[-1]["revenue_yoy"] if rows else None
    # TTM vs same period one year earlier (from quarterly)
    q = f.get("quarterly", {}).get("revenue", {})
    qe = sorted(q)
    if len(qe) >= 8:
        growth["revenue_ttm_yoy"] = (sum(q[e] for e in qe[-4:]) / sum(q[e] for e in qe[-8:-4]) - 1) * 100
        growth["latest_quarter_yoy"] = (q[qe[-1]] / q[qe[-5]] - 1) * 100 if q[qe[-5]] else None
    growth["quarterly_revenue"] = [[e, q[e]] for e in qe]

    # capital allocation (last 5 FY)
    last5 = rows[-5:]
    cap = {
        "buybacks_5y": _sum(r["buybacks"] for r in last5), "dividends_5y": _sum(r["dividends"] for r in last5),
        "fcf_5y": _sum(r["fcf"] for r in last5), "capex_5y": _sum(r["capex"] for r in last5),
        "sbc_5y": _sum(r["sbc"] for r in last5),
    }
    sh = series("diluted_shares")
    cap["share_count_cagr_5y"] = cagr(sh[-6][1], sh[-1][1], sh[-1][0] - sh[-6][0]) if len(sh) >= 6 else (
        cagr(sh[0][1], sh[-1][1], sh[-1][0] - sh[0][0]) if len(sh) >= 2 else None)
    if cap["fcf_5y"] and cap["fcf_5y"] > 0:
        cap["shareholder_return_pct_of_fcf"] = _pct((cap["buybacks_5y"] or 0) + (cap["dividends_5y"] or 0), cap["fcf_5y"])
    return {"rows": rows, "ttm": ttm, "balance": bal, "growth": growth, "capital": cap,
            "shares_outstanding": f.get("shares_outstanding"), "tags": f.get("tags", {}), "split_notes": split_notes, "currency": f.get("currency", "USD")}


def _pct(a, b):
    v = _safe_div(a, b)
    return v * 100 if v is not None else None


def _sum(it):
    vals = [x for x in it if x is not None]
    return sum(vals) if vals else None
