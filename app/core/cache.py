"""Two-tier cache: in-memory dict + JSON files on disk, TTL based, with single-flight locks
so concurrent requests for the same key trigger only one upstream fetch."""
import asyncio, hashlib, json, time
from typing import Any, Awaitable, Callable
from .config import CACHE_DIR

_mem: dict[str, tuple[float, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}


def _path(key: str):
    h = hashlib.sha1(key.encode()).hexdigest()[:20]
    safe = "".join(c if c.isalnum() else "_" for c in key)[:60]
    return CACHE_DIR / f"{safe}_{h}.json"


def get(key: str, ttl: float, allow_stale: bool = False):
    now = time.time()
    if key in _mem:
        ts, val = _mem[key]
        if now - ts < ttl or allow_stale:
            return val, ts
    p = _path(key)
    if p.exists():
        try:
            obj = json.loads(p.read_text())
            ts, val = obj["ts"], obj["val"]
            _mem[key] = (ts, val)
            if now - ts < ttl or allow_stale:
                return val, ts
        except Exception:
            pass
    return None, None


def put(key: str, val: Any, disk: bool = True):
    ts = time.time()
    _mem[key] = (ts, val)
    if disk:
        try:
            _path(key).write_text(json.dumps({"ts": ts, "key": key, "val": val}))
        except Exception:
            pass
    return ts


async def cached(key: str, ttl: float, fetch: Callable[[], Awaitable[Any]], disk: bool = True):
    """Returns (value, fetched_at_epoch, from_cache:bool, stale:bool). On upstream failure, serves
    stale cache if available (flagged stale) else re-raises."""
    val, ts = get(key, ttl)
    if val is not None:
        return val, ts, True, False
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        val, ts = get(key, ttl)
        if val is not None:
            return val, ts, True, False
        try:
            val = await fetch()
            ts = put(key, val, disk)
            return val, ts, False, False
        except Exception:
            sval, sts = get(key, ttl, allow_stale=True)
            if sval is not None:
                return sval, sts, True, True
            raise
