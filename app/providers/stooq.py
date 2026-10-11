"""Stooq daily CSV fallback for price history (used only if Yahoo chart fails)."""
import csv, io, datetime as dt
from ..core import cache
from ..core.http import client, SourceUnavailable

MAP = {"^GSPC": "^spx", "^IXIC": "^ndq", "^DJI": "^dji", "^RUT": "^rut", "^VIX": "^vix"}


async def chart(symbol: str) -> dict:
    s = MAP.get(symbol, symbol.lower().replace("-", ".") + ".us")
    url = f"https://stooq.com/q/d/l/?s={s}&i=d"

    async def fetch():
        r = await client().get(url, timeout=12)
        r.raise_for_status()
        rows = []
        for row in csv.DictReader(io.StringIO(r.text)):
            try:
                t = dt.datetime.strptime(row["Date"], "%Y-%m-%d").timestamp()
                c = float(row["Close"])
                rows.append([t, float(row["Open"]), float(row["High"]), float(row["Low"]), c,
                             float(row.get("Volume") or 0), c])
            except Exception:
                continue
        if not rows:
            raise SourceUnavailable("stooq empty")
        cut = rows[-1][0] - 5.2 * 365 * 86400
        rows = [r for r in rows if r[0] >= cut]
        return {"meta": {"symbol": symbol, "regularMarketPrice": rows[-1][4], "regularMarketTime": rows[-1][0]},
                "rows": rows}
    val, ts, _, stale = await cache.cached("stooq:" + s, 3600, fetch)
    return {"data": val, "fetched_at": ts, "stale": stale, "source": "Stooq (fallback, end-of-day)", "url": url}
