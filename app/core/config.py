import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "MarketVision AI research Jhon.cuthbertson@hotworx.net")
# A bare "Mozilla/5.0" works reliably with Yahoo/FRED from this host; full Chrome UA strings get 429s.
BROWSER_UA = "Mozilla/5.0"

# TTLs (seconds)
TTL_QUOTE = int(os.getenv("TTL_QUOTE", 120))
TTL_CHART = int(os.getenv("TTL_CHART", 900))
TTL_FRED = int(os.getenv("TTL_FRED", 6 * 3600))
TTL_SEC_FACTS = int(os.getenv("TTL_SEC_FACTS", 24 * 3600))
TTL_SEC_TICKERS = 7 * 24 * 3600
TTL_CALENDAR = 3 * 3600
TTL_SUMMARY = 6 * 3600
TTL_NEWS = 1800
TTL_LLM = 24 * 3600
TTL_SCANNER = 6 * 3600
