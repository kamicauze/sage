"""
Architect API Server - FastAPI backend for the Architect system.

This server provides REST endpoints for:
- Plan generation
- Build execution
- Memory search and management
- Usage statistics and budget tracking
- Real-time build progress via WebSockets

Usage:
    uvicorn architect.api.server:app --reload --port 8000

API Documentation:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""
import os
import sys
import traceback
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add project root to path
sys.path.append(os.getcwd())

from architect.api.routes import approvals, builds, chat, stats, memory, projects, news, google_workspace, webhooks, tasks, vault, agent_permissions, project_control
from architect.api.websocket import websocket_endpoint
from architect.api.models import HealthResponse, ErrorResponse, API_VERSION, API_COMPAT
from architect.api.security import (
    load_api_security_config,
    path_requires_auth,
    is_request_authorized,
)
from architect.logging_utils import (
    configure_logging,
    correlation_context,
    generate_correlation_id,
    log_event,
)

configure_logging()

BUILDS_GIT_IMPORT_ERROR = None
try:
    from architect.api.routes import builds_git
except Exception as exc:  # pragma: no cover - optional dependency resilience
    builds_git = None
    BUILDS_GIT_IMPORT_ERROR = exc

MCP_IMPORT_ERROR = None
try:
    from architect.api.routes import mcp
except Exception as exc:  # pragma: no cover - optional dependency resilience
    mcp = None
    MCP_IMPORT_ERROR = exc

# Create FastAPI app
app = FastAPI(
    title="Architect API",
    description="FastAPI backend for the Sage Architect system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

SECURITY = load_api_security_config()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=SECURITY.cors_origins,
    allow_credentials="*" not in SECURITY.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security + API version headers for backward-compatible clients
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    started = time.monotonic()
    correlation_id = (
        request.headers.get("x-architect-correlation-id", "").strip()
        or request.headers.get("x-request-id", "").strip()
        or generate_correlation_id("req")
    )
    request.state.correlation_id = correlation_id

    with correlation_context(correlation_id):
        log_event(
            "api",
            "request_received",
            method=request.method,
            path=request.url.path,
            client=str(request.client),
        )

        if path_requires_auth(request.url.path, SECURITY):
            if not is_request_authorized(request, SECURITY):
                log_event(
                    "api",
                    "request_unauthorized",
                    level="warning",
                    method=request.method,
                    path=request.url.path,
                )
                response = JSONResponse(
                    status_code=401,
                    content={
                        "error": "Unauthorized",
                        "detail": "Missing or invalid API token",
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                response.headers["X-Architect-Correlation-Id"] = correlation_id
                return response

        response = await call_next(request)
        response.headers["X-Architect-Api-Version"] = API_VERSION
        response.headers["X-Architect-Api-Compat"] = API_COMPAT
        response.headers["X-Architect-Auth-Required"] = "true" if SECURITY.auth_required else "false"
        response.headers["X-Architect-Correlation-Id"] = correlation_id
        log_event(
            "api",
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return response


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions."""
    correlation_id = getattr(request.state, "correlation_id", None) if request else None
    log_event(
        "api",
        "http_exception",
        level="warning",
        correlation_id=correlation_id,
        method=getattr(request, "method", None),
        path=str(getattr(request, "url", "")),
        status_code=exc.status_code,
        error=str(exc.detail),
    )
    error_response = ErrorResponse(
        error=exc.detail,
        detail=str(exc),
        timestamp=datetime.now()
    )
    response = JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(mode='json')
    )
    if correlation_id:
        response.headers["X-Architect-Correlation-Id"] = correlation_id
    return response


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    request_id = getattr(request.state, "correlation_id", None) if request else None
    if not request_id:
        request_id = generate_correlation_id("req")
    log_event(
        "api",
        "unhandled_exception",
        level="error",
        correlation_id=request_id,
        method=request.method,
        path=request.url.path,
        error=str(exc),
        traceback=traceback.format_exc(),
    )

    error_response = ErrorResponse(
        error="Internal server error",
        detail=f"Request ID: {request_id}",
        timestamp=datetime.now()
    )
    response = JSONResponse(
        status_code=500,
        content=error_response.model_dump(mode='json')
    )
    response.headers["X-Architect-Correlation-Id"] = request_id
    return response


# Include routers
app.include_router(projects.router)
app.include_router(builds.router)
if builds_git is not None:
    app.include_router(builds_git.router)  # Git-integrated builds
app.include_router(stats.router)
app.include_router(memory.router)
app.include_router(approvals.router)
app.include_router(chat.router)
app.include_router(news.router)
app.include_router(google_workspace.router)
app.include_router(webhooks.router)
app.include_router(tasks.router)
app.include_router(vault.router)
app.include_router(agent_permissions.router)
app.include_router(project_control.router)
if mcp is not None:
    app.include_router(mcp.router)  # MCP integrations


# Root endpoint
@app.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    """
    Root endpoint - API health check.

    Returns:
        HealthResponse with API status
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        architect_version="1.0.0"
    )


# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_route(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time build streaming.

    Connect to: ws://localhost:8000/ws/{client_id}

    Send JSON messages:
        {"action": "start_build", "build_id": "your-build-id"}
        {"action": "ping"}

    Receive real-time updates about build progress.
    """
    await websocket_endpoint(websocket, client_id)


# Startup/shutdown events
@app.on_event("startup")
async def startup_event():
    """Run on server startup."""
    log_event(
        "api",
        "startup",
        auth_required=SECURITY.auth_required,
        cors_origins=SECURITY.cors_origins,
        builds_git_enabled=BUILDS_GIT_IMPORT_ERROR is None,
        mcp_enabled=MCP_IMPORT_ERROR is None,
        builds_git_error=str(BUILDS_GIT_IMPORT_ERROR) if BUILDS_GIT_IMPORT_ERROR else None,
        mcp_error=str(MCP_IMPORT_ERROR) if MCP_IMPORT_ERROR else None,
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Run on server shutdown."""
    log_event("api", "shutdown")


if __name__ == "__main__":
    import uvicorn

    # Run server
    uvicorn.run(
        "architect.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
