"""Quick reachability probe for each upstream data source (prints status + latency)."""
import asyncio, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.providers import yahoo, fred, sec, nasdaq  # noqa: E402

async def t(name, coro):
    s = time.time()
    try:
        r = await asyncio.wait_for(coro, 60)
        print(f"OK   {name:22s} {time.time()-s:5.1f}s {str(r)[:80]!r}", flush=True)
    except Exception as e:
        print(f"FAIL {name:22s} {time.time()-s:5.1f}s {type(e).__name__}: {str(e)[:150]}", flush=True)

async def main():
    await t("yahoo chart SPY", yahoo.chart("SPY", "1mo", "1d"))
    await t("yahoo quote AAPL", yahoo.quotes(["AAPL"]))
    await t("yahoo summary AAPL", yahoo.summary("AAPL", "price"))
    await t("fred DGS10", fred.series("DGS10"))
    await t("sec tickers", sec.ticker_map())
    await t("nasdaq earnings", nasdaq.earnings(__import__("datetime").date.today()))
asyncio.run(main())
