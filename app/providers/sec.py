"""SEC EDGAR: ticker map, submissions (filings), companyfacts (XBRL). Fair-access User-Agent set."""
import datetime as dt
from ..core import cache
from ..core.config import TTL_SEC_TICKERS, TTL_SEC_FACTS
from ..core.http import sec_get, SourceUnavailable

SOURCE = "SEC EDGAR"


async def ticker_map() -> dict:
    async def fetch():
        r = await sec_get("https://www.sec.gov/files/company_tickers.json")
        out = {}
        for v in r.json().values():
            out[v["ticker"].upper()] = {"cik": int(v["cik_str"]), "name": v["title"]}
        return out
    val, *_ = await cache.cached("sec:tickers", TTL_SEC_TICKERS, fetch)
    return val


async def lookup(ticker: str):
    m = await ticker_map()
    t = ticker.upper()
    return m.get(t) or m.get(t.replace(".", "-")) or m.get(t.replace("-", "."))


async def submissions(cik: int) -> dict:
    url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"

    async def fetch():
        j = (await sec_get(url)).json()
        rec = j.get("filings", {}).get("recent", {})
        filings = []
        for i in range(min(len(rec.get("form", [])), 400)):
            form = rec["form"][i]
            if form not in ("10-K", "10-Q", "8-K", "20-F", "6-K", "40-F", "10-K/A", "DEF 14A", "S-1", "424B4"):
                continue
            acc = rec["accessionNumber"][i]
            doc = rec["primaryDocument"][i]
            filings.append({"form": form, "date": rec["filingDate"][i], "report_date": rec["reportDate"][i],
                            "items": rec.get("items", [""] * 9999)[i], "desc": rec.get("primaryDocDescription", [""] * 9999)[i],
                            "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc}"})
        return {"name": j.get("name"), "sic": j.get("sic"), "sic_desc": j.get("sicDescription"),
                "fiscal_year_end": j.get("fiscalYearEnd"), "exchanges": j.get("exchanges"), "tickers": j.get("tickers"),
                "state": j.get("stateOfIncorporation"), "website": j.get("website"), "category": j.get("category"),
                "filings": filings[:120]}
    val, ts, _, stale = await cache.cached(f"sec:sub:{cik}", TTL_SEC_FACTS, fetch)
    return {"data": val, "fetched_at": ts, "stale": stale, "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=&dateb=&owner=include&count=40"}


# ---------------- XBRL distillation ----------------
TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet", "RevenuesNetOfInterestExpense",
                "Revenue"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfSales"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss", "ProfitLossFromOperatingActivities"],
    "net_income": ["NetIncomeLoss", "ProfitLoss", "ProfitLossAttributableToOwnersOfParent"],
    "eps_diluted": ["EarningsPerShareDiluted", "DilutedEarningsLossPerShare"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
            "CashFlowsFromUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
              "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"],
    "rnd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "dividends": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "diluted_shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}
INSTANT = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
             "CashAndCashEquivalents"],
    "st_investments": ["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
    "lt_debt_total": ["LongTermDebt"],
    "lt_debt_noncurrent": ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"],
    "debt_current": ["LongTermDebtCurrent", "DebtCurrent"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "Equity"],
    "assets": ["Assets"],
}
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "10-KT"}
Q_FORMS = ANNUAL_FORMS | {"10-Q", "10-Q/A", "6-K"}


def _d(s):
    return dt.date.fromisoformat(s)


def _units(fact, prefer):
    u = fact.get("units", {})
    if prefer == "USD":
        # Foreign filers may add USD "convenience translations" for a year or two; use the currency with
        # the deepest history (the reporting currency) unless USD is comparably complete.
        money = {k: v for k, v in u.items() if "/" not in k and k not in ("shares", "pure")}
        if not money:
            return None, []
        best = max(money, key=lambda k: len(money[k]))
        if "USD" in money and len(money["USD"]) >= 0.8 * len(money[best]):
            return "USD", money["USD"]
        return best, money[best]
    if prefer in u:
        return prefer, u[prefer]
    if prefer == "USD/shares":
        for k, v in u.items():
            if k.endswith("/shares"):
                return k, v
    return None, []


_UNIT_SEEN = {}


def _collect(facts, tags, unit, mode="priority"):
    """Merge tags by priority: for each period key, first tag in list that reports it wins.
    Returns {(start,end): (val, filed, form, tag)} and the tags used."""
    out, used = {}, []
    for ns in ("us-gaap", "ifrs-full"):
        f = facts.get(ns) or {}
        for tag in tags:
            if tag not in f:
                continue
            u, entries = _units(f[tag], unit)
            if entries and tags is TAGS["revenue"]:
                _UNIT_SEEN.setdefault("revenue", u)
            hit = False
            for e in entries:
                if e.get("form") not in Q_FORMS:
                    continue
                k = (e.get("start"), e["end"])
                cur = out.get(k)
                if cur and cur[3] != tag:
                    # priority mode: higher-priority tag already supplied this period.
                    # max mode (revenue): keep the larger total, since component tags (e.g. fee revenue) understate.
                    if mode != "max" or e["val"] <= cur[0]:
                        continue
                    cur = None
                if cur is None or e["filed"] > cur[1]:
                    out[k] = (e["val"], e["filed"], e["form"], tag)
                    hit = True
            if hit:
                used.append(f"{ns}:{tag}")
    return out, used


def _annual(col):
    res = {}
    for (s, e), (v, filed, form, tag) in col.items():
        if not s:
            continue
        days = (_d(e) - _d(s)).days
        if 330 <= days <= 400 and form in ANNUAL_FORMS:
            res[e] = {"start": s, "end": e, "val": v, "tag": tag}
    return dict(sorted(res.items()))


def _quarters(col, annual):
    """Derive discrete quarter values from 3-month entries and from YTD differences; fill Q4 from annual."""
    q = {}
    by_start = {}
    for (s, e), (v, *_rest) in col.items():
        if not s:
            continue
        days = (_d(e) - _d(s)).days
        if 80 <= days <= 100:
            q[e] = (s, v)
        if 80 <= days <= 400:
            by_start.setdefault(s, []).append((e, v, days))
    for s, lst in by_start.items():
        lst.sort()
        for i in range(1, len(lst)):
            e0, v0, d0 = lst[i - 1]
            e1, v1, d1 = lst[i]
            if 80 <= d1 - d0 <= 100 and e1 not in q:
                q[e1] = (e0, v1 - v0)
    for e, a in annual.items():
        if e in q:
            continue
        inside = [(qe, qv) for qe, (qs, qv) in q.items() if a["start"] <= qs and qe < e and qe > a["start"]]
        if len(inside) == 3:
            q[e] = (max(x[0] for x in inside), a["val"] - sum(x[1] for x in inside))
    return dict(sorted(q.items()))


def _ttm(q, annual):
    if not q:
        return None
    ends = sorted(q)
    last = ends[-4:]
    if len(last) < 4:
        return None
    span = (_d(last[-1]) - _d(last[0])).days
    if not (250 <= span <= 290):
        return None
    if annual and max(annual) >= last[-1]:
        a = annual[max(annual)]
        return {"val": a["val"], "end": a["end"], "method": "latest fiscal year (no newer quarters)"}
    return {"val": sum(q[e][1] for e in last), "end": last[-1], "method": "sum of last 4 reported/derived quarters"}


def _instants(facts, tags):
    col, used = {}, []
    for ns in ("us-gaap", "ifrs-full"):
        f = facts.get(ns) or {}
        for tag in tags:
            if tag not in f:
                continue
            u, entries = _units(f[tag], "USD")
            hit = False
            for e in entries:
                if e.get("form") not in Q_FORMS or e.get("start"):
                    continue
                cur = col.get(e["end"])
                if cur and cur[3] != tag:
                    continue
                if cur is None or e["filed"] > cur[1]:
                    col[e["end"]] = (e["val"], e["filed"], e["form"], tag)
                    hit = True
            if hit:
                used.append(f"{ns}:{tag}")
    return dict(sorted(col.items())), used


def distill(j: dict) -> dict:
    facts = j.get("facts", {})
    _UNIT_SEEN.clear()
    out = {"entity": j.get("entityName"), "annual": {}, "ttm": {}, "quarterly": {}, "instant": {}, "tags": {},
           "currency": "USD"}
    for k, tags in TAGS.items():
        unit = "USD/shares" if k == "eps_diluted" else ("shares" if k == "diluted_shares" else "USD")
        col, used = _collect(facts, tags, unit, "max" if k == "revenue" else "priority")
        ann = _annual(col)
        out["annual"][k] = {e: v["val"] for e, v in ann.items()}
        out["tags"][k] = used
        if k not in ("eps_diluted", "diluted_shares"):
            qs = _quarters(col, ann)
            out["quarterly"][k] = {e: v for e, (_, v) in list(qs.items())[-12:]}
            t = _ttm(qs, ann)
            if t:
                out["ttm"][k] = t
        if k == "revenue" and ann:
            # record fiscal period boundaries
            out["fy_periods"] = {e: v["start"] for e, v in ann.items()}
    for k, tags in INSTANT.items():
        col, used = _instants(facts, tags)
        out["instant"][k] = {e: v[0] for e, v in list(col.items())[-24:]}
        out["tags"][k] = used
    out["currency"] = _UNIT_SEEN.get("revenue") or "USD"
    # gross profit fallback = revenue - cost of revenue
    if not out["annual"]["gross_profit"] and out["annual"]["cost_of_revenue"]:
        r, c = out["annual"]["revenue"], out["annual"]["cost_of_revenue"]
        out["annual"]["gross_profit"] = {e: r[e] - c[e] for e in r if e in c}
        out["tags"]["gross_profit"] = ["derived: revenue - cost_of_revenue"]
    # shares outstanding (dei), summed across classes for the latest date
    so = (facts.get("dei") or {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    if so:
        latest = max(e["end"] for e in so)
        accs = {}
        for e in so:
            if e["end"] == latest:
                accs.setdefault(e["accn"], 0)
                accs[e["accn"]] += e["val"]
        out["shares_outstanding"] = {"val": max(accs.values()), "as_of": latest}
    return out


async def facts(cik: int) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

    async def fetch():
        r = await sec_get(url)
        return distill(r.json())
    try:
        val, ts, _, stale = await cache.cached(f"sec:facts:{cik}", TTL_SEC_FACTS, fetch)
    except Exception as e:
        raise SourceUnavailable(f"SEC companyfacts unavailable: {e}")
    return {"data": val, "fetched_at": ts, "stale": stale, "url": url}
