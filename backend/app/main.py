from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.ratelimit import RateLimiter
from .api.routes import router
from .config import Settings
from .errors import ScanError
from .services.ai.service import AiService
from .services.report_store import ReportStore
from .services.scan_manager import ScanManager
from .utils.fs import ensure_within

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    settings.ensure_dirs()
    store = ReportStore(settings.data_dir)
    manager = ScanManager(settings, store)
    ai_service = AiService(settings, store)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        manager.shutdown()

    app = FastAPI(
        title="RepoReady · Git 仓库接入体检",
        description="公开 GitHub / Gitee 仓库的接入就绪度体检 API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.report_store = store
    app.state.scan_manager = manager
    app.state.ai_service = ai_service
    app.state.scan_limiter = RateLimiter(settings.rate_limit_per_minute, 60)
    app.state.ai_limiter = RateLimiter(10, 60)
    app.state.update_cache: dict[str, tuple[float, object]] = {}
    app.state.update_cache_lock = threading.Lock()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.dev_cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=800)
    app.include_router(router)

    @app.exception_handler(ScanError)
    async def scan_error_handler(_request: Request, exc: ScanError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        message = str(first.get("msg") or "请求参数不合法")
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "INVALID_REQUEST",
                "message": message,
                "details": str(first.get("loc") or ""),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": "HTTP_ERROR",
                "message": str(exc.detail),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error")
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "服务器内部错误，请稍后重试",
            },
        )

    dist = Path(settings.frontend_dist)
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise ScanError("NOT_FOUND", "接口不存在", http_status=404)
        index = dist / "index.html"
        if not index.exists():
            return HTMLResponse(
                "<html><body style='background:#0B1220;color:#E7EDF7;font-family:sans-serif;"
                "padding:40px'><h1>RepoReady 后端已启动</h1>"
                "<p>前端尚未构建。请运行 <code>start.bat</code>，或手动执行 "
                "<code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>。</p>"
                "<p>开发模式请访问 <code>http://127.0.0.1:5173</code>。</p></body></html>",
                status_code=503,
            )
        if full_path:
            candidate = (dist / full_path).resolve()
            if candidate.is_file() and ensure_within(dist, candidate):
                return FileResponse(candidate)
        return FileResponse(index)

    return app


app = create_app()
