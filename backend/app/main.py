"""
FastAPI main application — app setup, lifespan, middleware, exception handlers.
Route logic lives in backend/app/routers/.
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from . import database, vector_db, graph_db, face_service, sync_worker, auth
from .routers import (
    auth as auth_router, chat as chat_router, sessions as sessions_router,
    persons as persons_router, upload as upload_router,
    ideas as ideas_router, content as content_router,
    projects as projects_router, entities as entities_router,
)
from .routers.deps import limiter, UPLOAD_DIR

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))

# ---------------------------------------------------------------------------
# Standardized error helpers
# ---------------------------------------------------------------------------
def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Return a JSONResponse with the standardized error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _status_to_code(status_code: int, detail: str) -> str:
    """Map HTTP status + detail text to a machine-readable error code."""
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "ACCESS_DENIED",
        404: "NOT_FOUND",
        413: "PAYLOAD_TOO_LARGE",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
    }
    return mapping.get(status_code, f"ERROR_{status_code}")


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Initialize databases
# ---------------------------------------------------------------------------
database.init_db()

try:
    vector_db.init_vector_db()
    logger.info("pgvector initialized successfully")
except Exception as e:
    logger.warning("Could not initialize pgvector: %s. Semantic search may not work.", e)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):
    """Startup: eagerly load heavy models + init Neo4j. Shutdown: release connection pools."""
    logger.info("Starting Engram backend...")
    await run_in_threadpool(face_service.init_face_model)
    try:
        await graph_db.init_graph_db()
        logger.info("Neo4j knowledge graph initialized successfully")
    except Exception as e:
        logger.warning("Could not initialize Neo4j: %s. Person identity features may not work.", e)

    os.makedirs(DATA_DIR, exist_ok=True)
    logger.info("Data directory ready: %s", DATA_DIR)

    # Optional: rebuild indexes on startup for recovery
    if os.environ.get("REBUILD_INDEX_ON_START", "").lower() == "true":
        from app.md_storage import rebuild_index
        for etype in ("idea", "content", "project"):
            # Runs per-user; for now use a sentinel or scan data dir
            logger.info("Startup rebuild_index for %s", etype)

    sync_task = asyncio.create_task(sync_worker.run_sync_worker())
    logger.info("Engram backend ready")
    yield
    logger.info("Shutting down Engram backend...")
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    await graph_db.Neo4jConnection.close()
    vector_db.close_pool()
    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Chat API",
    description="FastAPI backend for chat application with LangChain",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning("Rate limit exceeded: client=%s path=%s", request.client.host if request.client else "-", request.url.path)
    return error_response(429, "RATE_LIMIT_EXCEEDED", f"Rate limit exceeded: {exc.detail}")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return error_response(exc.status_code, exc.detail["code"], exc.detail["message"])
    code = _status_to_code(exc.status_code, str(exc.detail))
    return error_response(exc.status_code, code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    messages = "; ".join(
        f"{'.'.join(str(l) for l in e['loc'][1:])}: {e['msg']}" for e in exc.errors()
    )
    return error_response(422, "VALIDATION_ERROR", messages)


# ---------------------------------------------------------------------------
# Static files & middleware
# ---------------------------------------------------------------------------
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://192.168.1.12:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info(
        "method=%s path=%s status=%d duration_ms=%.1f client=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request.client.host if request.client else "-",
    )
    return response


# ---------------------------------------------------------------------------
# Health / admin endpoints (kept here — too small to warrant a router)
# ---------------------------------------------------------------------------
@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Chat API is running"}


@app.get("/readyz")
def readiness_check():
    """Readiness probe — returns 503 until the face model is loaded."""
    if not face_service.is_model_ready():
        return Response(status_code=503, content="Face model loading...")
    return {"status": "ready"}


@app.get("/api/v1/admin/pending-syncs")
async def pending_sync_stats(
    current_user: database.User = Depends(auth.get_current_user),
):
    """Return counts of pending/failed embedding sync operations."""
    stats = await run_in_threadpool(vector_db.get_pending_sync_stats)
    return stats


@app.post("/api/v1/admin/rebuild-index")
async def admin_rebuild_index(
    entity_type: str = Query(..., description="Entity type: idea, content, or project"),
    current_user: database.User = Depends(auth.get_current_user),
):
    """Rebuild the _index.json for a given entity type from .md files on disk."""
    from .md_storage import rebuild_index

    if entity_type not in ("idea", "content", "project"):
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": f"Invalid entity_type: {entity_type}"})

    new_index = await rebuild_index(str(current_user.id), entity_type)
    return {"status": "ok", "entity_type": entity_type, "total": len(new_index)}


# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(sessions_router.router)
app.include_router(chat_router.router)
app.include_router(persons_router.router)
app.include_router(ideas_router.router)
app.include_router(content_router.router)
app.include_router(projects_router.router)
app.include_router(entities_router.router)
app.include_router(upload_router.router)
