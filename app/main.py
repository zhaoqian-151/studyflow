import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.middleware import BodyLimitMiddleware
from app.routes import auth, chat, intelligence, learning
from app.schema import verify_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("studyflow.http")
STATIC = Path(__file__).parent / "static"
attempts = defaultdict(deque)


@asynccontextmanager
async def lifespan(app):
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
    else:
        verify_schema(engine)
    logger.info(
        "AI configuration loaded: chat_mode=%s model=%s retrieval_mode=%s",
        "llm" if settings.ai_api_key else "rules",
        settings.ai_model if settings.ai_api_key else "none",
        "hybrid" if settings.embedding_api_key else "bm25",
    )
    yield
    engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="学习管理、可追踪的 AI 规划工作流与知识库问答",
    lifespan=lifespan,
)


@app.middleware("http")
async def guard_and_log(request: Request, call_next):
    request_id = uuid4().hex[:12]
    started = time.perf_counter()
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "不允许跨站写入请求"}, status_code=403)
        try:
            if int(request.headers.get("content-length", 0)) > 6 * 1024 * 1024:
                return JSONResponse({"detail": "请求体最多 6 MB"}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "无效的请求长度"}, status_code=400)
    if request.url.path in {"/api/auth/login", "/api/auth/register"} and request.method == "POST":
        key = request.client.host if request.client else "unknown"
        current = time.monotonic()
        for stale in [ip for ip, values in attempts.items() if not values or values[-1] < current - 60]:
            attempts.pop(stale, None)
        queue = attempts[key]
        while queue and queue[0] < current - 60:
            queue.popleft()
        if len(queue) >= 20:
            return JSONResponse({"detail": "操作过于频繁，请一分钟后再试"}, status_code=429)
        queue.append(current)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    # Swagger/ReDoc load their own CDN scripts and inline bootstrap code.
    if request.url.path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    logger.info(
        "%s %s status=%s duration_ms=%.1f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
        request_id,
    )
    return response


app.add_middleware(BodyLimitMiddleware)
app.include_router(auth.router)
app.include_router(learning.router)
app.include_router(intelligence.router)
app.include_router(chat.router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/health", tags=["运行状态"])
def health():
    from sqlalchemy import text

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "version": app.version,
        "database": engine.dialect.name,
        "vector_store": "pgvector" if engine.dialect.name == "postgresql" else "json-test-fallback",
    }


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")
