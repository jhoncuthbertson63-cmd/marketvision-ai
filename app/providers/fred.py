"""FRED public CSV (no key): https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIES"""
import csv, io
from ..core import cache
from ..core.config import TTL_FRED, SEC_USER_AGENT
import asyncio
from ..core.http import get_retry, SourceUnavailable
_sem = asyncio.Semaphore(2)


async def series(sid: str) -> dict:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

    async def fetch():
        async with _sem:
            # FRED rejects a bare browser UA from cloud runners; a descriptive UA works everywhere.
            r = await get_retry(url, tries=4, timeout=30, headers={"User-Agent": SEC_USER_AGENT})
        out = []
        rd = csv.reader(io.StringIO(r.text))
        next(rd, None)
        for row in rd:
            if len(row) < 2 or row[1] in (".", ""):
                continue
            try:
                out.append([row[0], float(row[1])])
            except ValueError:
                pass
        if not out:
            raise SourceUnavailable("FRED empty")
        return out
    val, ts, _, stale = await cache.cached("fred:" + sid, TTL_FRED, fetch)
    return {"data": val, "fetched_at": ts, "stale": stale, "url": f"https://fred.stlouisfed.org/series/{sid}"}
