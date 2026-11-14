"""
ClaraMed FastAPI Application

Main application entry point for the ClaraMed backend API.
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time
import uuid

from backend.core.config import settings, storage_topology_warning, production_config_errors
from backend.core.logging import configure_logging, get_logger
from backend.core.exceptions import ClaraMedException
from backend.api.routes import health, analyses, integration

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("=" * 60)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info("=" * 60)
    
    problems = production_config_errors(
        settings.APP_ENV, settings.DEBUG, settings.API_KEY_HASH_SECRET, settings.SECRET_KEY)
    if problems:
        raise RuntimeError("Refusing to start with an unsafe production configuration: " + "; ".join(problems))
    
    topology = storage_topology_warning(
        settings.APP_ENV, settings.STORAGE_PROVIDER, settings.STORAGE_SHARED_CONFIRMED)
    if topology:
        logger.warning(topology)
    
    # Validate configuration
    missing = settings.validate_required_settings()
    if missing:
        logger.warning("Missing required configuration:")
        for item in missing:
            logger.warning(f"  - {item}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ClaraMed API")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Medical Analysis Platform",
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID and timing middleware
@app.middleware("http")
async def add_request_metadata(request: Request, call_next):
    """Add request ID and timing to all requests."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    
    logger.info(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        process_time=f"{process_time:.3f}s",
        request_id=request_id,
    )
    
    return response


# Exception handlers
@app.exception_handler(ClaraMedException)
async def claramed_exception_handler(request: Request, exc: ClaraMedException):
    """Handle ClaraMed custom exceptions."""
    logger.error(
        "ClaraMed exception",
        error=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        request_id=getattr(request.state, "request_id", None),
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


def _safe_validation_errors(errors) -> list:
    """JSON-safe validation errors without echoing request input (which may contain patient data)."""
    safe = []
    for err in errors:
        item = {k: v for k, v in err.items() if k not in ("input", "ctx", "url")}
        item["loc"] = [str(part) for part in err.get("loc", ())]
        if err.get("ctx"):
            item["ctx"] = {k: str(v) for k, v in err["ctx"].items()}
        safe.append(item)
    return safe


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    details = _safe_validation_errors(exc.errors())
    logger.warning(
        "Validation error",
        errors=details,
        request_id=getattr(request.state, "request_id", None),
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "message": "Validation error",
                "details": details,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(
        "Unexpected error",
        error=str(exc),
        request_id=getattr(request.state, "request_id", None),
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "Internal server error",
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(analyses.router, prefix="/api/v1", tags=["Analyses"])
app.include_router(integration.router, prefix="/api/v1", tags=["Integration"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/api/docs" if settings.DEBUG else "disabled",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
