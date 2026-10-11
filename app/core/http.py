import asyncio, time
import httpx
from .config import SEC_USER_AGENT, BROWSER_UA

_client: httpx.AsyncClient | None = None
_sec_client: httpx.AsyncClient | None = None
_sec_sem = asyncio.Semaphore(4)
_sec_last = [0.0]


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0), follow_redirects=True,
                                    headers={"User-Agent": BROWSER_UA, "Accept": "application/json, text/plain, */*"})
    return _client


def sec_client() -> httpx.AsyncClient:
    global _sec_client
    if _sec_client is None:
        _sec_client = httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0), follow_redirects=True,
                                        headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    return _sec_client


async def sec_get(url: str) -> httpx.Response:
    """SEC fair-access: <=10 req/s. We stay well below (~6/s) with a semaphore + spacing."""
    async with _sec_sem:
        wait = 0.16 - (time.time() - _sec_last[0])
        if wait > 0:
            await asyncio.sleep(wait)
        _sec_last[0] = time.time()
        r = await sec_client().get(url)
        r.raise_for_status()
        return r


async def get_retry(url, tries=3, **kw):
    """GET with backoff on 429/5xx and transient network errors."""
    last = None
    for i in range(tries):
        try:
            r = await client().get(url, **kw)
            if r.status_code in (429, 500, 502, 503, 504) and i < tries - 1:
                await asyncio.sleep(1.5 * (i + 1))
                continue
            r.raise_for_status()
            return r
        except (httpx.TransportError,) as e:
            last = e
            await asyncio.sleep(1.0 * (i + 1))
    if last:
        raise last
    r.raise_for_status()
    return r


class SourceUnavailable(Exception):
    pass


def meta(source: str, url: str | None, fetched_at: float | None, *, delayed: str | None = None,
         as_of: str | None = None, stale: bool = False, kind: str = "fact", note: str | None = None):
    """Uniform attribution block attached to every data payload."""
    return {"source": source, "url": url, "fetched_at": fetched_at, "as_of": as_of, "delayed": delayed,
            "stale": stale, "kind": kind, "note": note}
