"""Nasdaq.com public calendar JSON (earnings + economic events). Unofficial; may change."""
import datetime as dt, html
from ..core import cache
from ..core.config import TTL_CALENDAR
from ..core.http import client

H = {"Accept": "application/json", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}


def _money(s):
    try:
        return float(str(s).replace("$", "").replace(",", ""))
    except Exception:
        return None


async def earnings(day: dt.date) -> dict:
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={day.isoformat()}"

    async def fetch():
        r = await client().get(url, headers=H, timeout=15)
        r.raise_for_status()
        rows = ((r.json().get("data") or {}).get("rows")) or []
        return [{"date": day.isoformat(), "symbol": x.get("symbol"), "name": x.get("name"), "time": x.get("time"),
                 "market_cap": _money(x.get("marketCap")), "eps_forecast": x.get("epsForecast"),
                 "n_ests": x.get("noOfEsts"), "fiscal_q": x.get("fiscalQuarterEnding"),
                 "last_year_eps": x.get("lastYearEPS")} for x in rows]
    val, ts, _, stale = await cache.cached("ndq_earn:" + day.isoformat(), TTL_CALENDAR, fetch)
    return {"data": val, "fetched_at": ts, "stale": stale}


async def economic(day: dt.date) -> dict:
    url = f"https://api.nasdaq.com/api/calendar/economicevents?date={day.isoformat()}"

    async def fetch():
        r = await client().get(url, headers=H, timeout=15)
        r.raise_for_status()
        rows = ((r.json().get("data") or {}).get("rows")) or []
        clean = lambda s: html.unescape(str(s or "")).replace("\xa0", "").strip()
        return [{"date": day.isoformat(), "gmt": x.get("gmt"), "country": x.get("country"),
                 "event": clean(x.get("eventName")), "actual": clean(x.get("actual")),
                 "consensus": clean(x.get("consensus")), "previous": clean(x.get("previous"))} for x in rows]
    val, ts, _, stale = await cache.cached("ndq_econ:" + day.isoformat(), TTL_CALENDAR, fetch)
    return {"data": val, "fetched_at": ts, "stale": stale}
