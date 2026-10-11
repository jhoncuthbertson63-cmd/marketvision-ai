import asyncio, datetime as dt, time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def iso(ts):
    if ts is None:
        return None
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).isoformat()


def delay_label(q: dict | None):
    if not q:
        return "Delayed / end-of-day (Yahoo Finance)"
    state = q.get("marketState") or ""
    d = q.get("exchangeDataDelayedBy")
    t = q.get("regularMarketTime")
    when = dt.datetime.fromtimestamp(t, tz=ET).strftime("%b %d %I:%M %p ET") if t else "unknown time"
    base = f"Delayed {d} min" if d else "Delayed (exchange delay varies, typically ≥15 min; some feeds real-time)"
    if state and state not in ("REGULAR",):
        return f"Market {state.lower()} — last regular-session price as of {when}. {base}."
    return f"{base}. Last trade time {when}."


async def gather_limited(coros, n=8):
    sem = asyncio.Semaphore(n)

    async def run(c):
        async with sem:
            try:
                return await c
            except Exception as e:
                return e
    return await asyncio.gather(*(run(c) for c in coros))


def M(source, url, fetched_at, kind="fact", delayed=None, stale=False, note=None, as_of=None):
    return {"source": source, "url": url, "fetched_at": iso(fetched_at), "kind": kind, "delayed": delayed,
            "stale": stale, "note": note, "as_of": as_of}
