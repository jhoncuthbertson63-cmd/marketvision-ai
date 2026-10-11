"""Static snapshot builder for GitHub Pages (or any static host).
Runs the same fetchers/analysis as the live server and writes JSON the frontend reads.
Usage: python scripts/build_static.py [--out site] [--research all|none|LIST] [--max-age-h 20] [--limit N]"""
import argparse, asyncio, datetime as dt, json, os, re, shutil, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.modules import dashboard, scanner, research, registry  # noqa: E402
from app.analysis.universe import HEATMAP, INDUSTRIES  # noqa: E402
from app.core import llm  # noqa: E402

REPORT_STORE = ROOT / "data" / "static_reports"


def universe():
    ic = json.loads((ROOT / "data" / "index_constituents.json").read_text())
    sc = json.loads((ROOT / "data" / "smallcaps.json").read_text())["tickers"]
    s = set(ic.get("sp500", [])) | set(ic.get("nasdaq100", [])) | set(sc)
    s |= {c for i in INDUSTRIES for c in i["companies"]} | {c for v in HEATMAP.values() for c in v}
    s |= {"SPY", "QQQ", "DIA", "IWM"}
    ex = ROOT / "data" / "extra_tickers.json"  # tickers requested via GitHub issues
    if ex.exists():
        s |= set(json.loads(ex.read_text()).get("tickers", []))
    return sorted(t for t in s if re.fullmatch(r"[A-Z0-9\-]{1,10}", t))


def slim(rep):
    """Shrink price history: daily for last 400 bars, weekly before that."""
    h = rep.get("price_history") or []
    if len(h) > 400:
        old, recent = h[:-400], h[-400:]
        rep["price_history"] = old[::5] + recent
    return rep


def dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), default=str))


async def build_research(tickers, out: Path, max_age_h: float, conc: int):
    REPORT_STORE.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(conc)
    ok, fail, reused = [], {}, 0
    budget = float(os.getenv("RESEARCH_BUDGET_MIN", 40)) * 60
    t_start = time.time(); done = [0]

    async def one(t):
        nonlocal reused
        store = REPORT_STORE / f"{t}.json"
        if store.exists() and time.time() - store.stat().st_mtime < max_age_h * 3600:
            reused += 1
            ok.append(t)
            return
        async with sem:
            if time.time() - t_start > budget:
                fail[t] = "skipped: build time budget reached"
                if store.exists(): ok.append(t)
                return
            try:
                rep = await asyncio.wait_for(research.research(t, narrative_mode="rule"), 180)
                dump(store, slim(rep))
                ok.append(t)
            except Exception as e:
                msg = getattr(e, "detail", None) or f"{type(e).__name__}"
                fail[t] = str(msg)[:160]
                if store.exists():  # keep last good report (it carries its own timestamp)
                    ok.append(t)
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"  research progress {done[0]}/{len(tickers)-reused} built, {len(fail)} failed, {time.time()-t_start:.0f}s", flush=True)
    t0 = time.time()
    await asyncio.gather(*(one(t) for t in tickers))
    dest = out / "data" / "research"
    dest.mkdir(parents=True, exist_ok=True)
    names = {}
    for t in ok:
        src = REPORT_STORE / f"{t}.json"
        if src.exists():
            shutil.copyfile(src, dest / f"{t}.json")
            try:
                j = json.loads(src.read_text())
                names[t] = {"name": j.get("name"), "generated_at": j.get("generated_at")}
            except Exception:
                pass
    print(f"research: {len(names)} reports ({reused} reused from <{max_age_h}h store), {len(fail)} failed, {time.time()-t0:.0f}s", flush=True)
    return names, fail


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "site"))
    ap.add_argument("--research", default="all")
    ap.add_argument("--max-age-h", type=float, default=float(os.getenv("RESEARCH_MAX_AGE_H", 20)))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--conc", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "static", out / "static")
    started = dt.datetime.now(dt.timezone.utc)
    errors = {}

    async def save(name, coro):
        try:
            t0 = time.time(); dump(out / "data" / f"{name}.json", await asyncio.wait_for(coro, 300)); print(f"  {name}: {time.time()-t0:.0f}s", flush=True)
        except Exception as e:
            errors[name] = f"{type(e).__name__}: {str(e)[:150]}"
            dump(out / "data" / f"{name}.json", {"error": f"Data unavailable at snapshot time ({type(e).__name__})."})
    await save("dashboard/indexes", dashboard.indexes())
    await save("dashboard/sectors", dashboard.sectors())
    await save("dashboard/macro", dashboard.macro())
    await save("dashboard/heatmap", dashboard.heatmap())
    await save("dashboard/calendar", dashboard.calendar())
    await save("scanner", scanner.get_scanner())
    await save("radar", scanner.radar())
    print("dashboard+scanner done", errors or "", flush=True)

    uni = universe()
    if a.research == "none":
        tick = []
    elif a.research == "all":
        tick = uni
    else:
        tick = [t.strip().upper() for t in a.research.split(",") if t.strip()]
    if a.limit:
        tick = tick[:a.limit]
    # include previously stored reports even if not rebuilt this run
    names, fail = await build_research(tick, out, a.max_age_h, a.conc)
    for p in REPORT_STORE.glob("*.json"):
        t = p.stem
        if t not in names:
            shutil.copyfile(p, out / "data" / "research" / p.name)
            j = json.loads(p.read_text())
            names[t] = {"name": j.get("name"), "generated_at": j.get("generated_at")}
    finished = dt.datetime.now(dt.timezone.utc)
    dump(out / "data" / "tickers.json", {"tickers": names, "universe_size": len(uni)})
    dump(out / "data" / "modules.json", {"modules": [{k: v for k, v in m.items() if k != "router"} for m in registry.MODULES],
                                         "llm": {"configured": False, "provider": None, "static": True}})
    dump(out / "data" / "meta.json", {"snapshot_started": started.isoformat(), "snapshot_finished": finished.isoformat(),
                                      "errors": errors, "research_failures": fail, "research_count": len(names),
                                      "schedule": os.getenv("MV_SCHEDULE_TEXT", "Every 30 min during US market hours (Mon–Fri), plus a daily full rebuild"),
                                      "repo": os.getenv("GITHUB_REPOSITORY")})
    html = (ROOT / "static" / "index.html").read_text()
    html = html.replace("<head>", "<head>\n<script>window.MV_STATIC=true;</script>", 1)
    (out / "index.html").write_text(html)
    (out / "404.html").write_text(html)
    (out / ".nojekyll").write_text("")
    print(f"site written to {out} in {(finished-started).total_seconds():.0f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
