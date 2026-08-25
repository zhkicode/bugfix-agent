import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.init_db import init_db
from app.routers import containers, dashboard, servers, settings, tasks
from app.services.scheduler import scheduler  # noqa: E402 实例而非模块

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await scheduler.start()
    yield
    await scheduler.shutdown()


app = FastAPI(title="BugfixAgent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(servers.router)
app.include_router(containers.router)
app.include_router(tasks.router)
app.include_router(settings.router)
app.include_router(dashboard.router)


@app.get("/api/health")
async def health():
    return {"ok": True}


# 生产模式：托管前端构建产物
_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")

    # SPA history 路由回退：/containers 等子路径直接访问或刷新时不返回 404
    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request, exc: StarletteHTTPException):
        if (
            exc.status_code == 404
            and request.method == "GET"
            and not request.url.path.startswith("/api")
        ):
            return FileResponse(_dist / "index.html")
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
