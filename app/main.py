from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api.middleware import RequestIDMiddleware
from app.api.routes import health, documents, queries, venues


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    setup_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="TeloHive Venue Knowledge Assistant",
        description=(
            "RAG-powered API for querying venue knowledge. "
            "Supports document ingestion, hybrid retrieval, "
            "and grounded answer generation with citations."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(RequestIDMiddleware)

    # Routes
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(queries.router, prefix="/api/v1")
    app.include_router(venues.router, prefix="/api/v1")

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "detail": str(exc) if settings.app_env == "development" else None,
                "request_id": request_id,
            },
        )

    return app


app = create_app()