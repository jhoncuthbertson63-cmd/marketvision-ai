import asyncio, logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .modules import registry
from .core import llm

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="MarketVision AI", version="0.1.0-stage1")
app.add_middleware(GZipMiddleware, minimum_size=1000)
log = logging.getLogger("uvicorn.error")

for m in registry.MODULES:
    if m.get("router") is not None:
        app.include_router(m["router"])


@app.get("/api/health")
async def health():
    return {"ok": True, "llm": llm.status()}


@app.get("/api/modules")
async def modules():
    return {"modules": [{k: v for k, v in m.items() if k != "router"} for m in registry.MODULES], "llm": llm.status()}


@app.exception_handler(Exception)
async def err(request, exc):
    log.exception("unhandled")
    return JSONResponse({"error": f"Internal error: {type(exc).__name__}: {str(exc)[:200]}"}, status_code=500)


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
async def index():
    return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-cache"})


@app.on_event("startup")
async def warm():
    async def run():
        await asyncio.sleep(2)
        try:
            from .modules import dashboard, scanner
            await dashboard.indexes()
            await dashboard.heatmap()
            await scanner.warm()
            log.info("warmup complete")
        except Exception as e:
            log.warning(f"warmup failed: {e}")
    asyncio.create_task(run())
