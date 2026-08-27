"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import validation_error_handler
from app.routers.catalog import router as catalog_router
from app.routers.quotes import router as quotes_router

settings = get_settings()

# Uvicorn configures its own loggers and nothing else, so without this the application's own
# INFO lines -- the stored-quote records and, in development, the mail the mailer would have
# sent -- go nowhere at all.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="TruckBuild API",
    version="0.1.0",
    description="Catalog, configurator pricing, and quote submission for TruckBuild.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Every rejection leaves this API in one shape, FastAPI's own 422 included, so the web app
# has a single error body to parse and render beside the field at fault. See app/errors.py.
app.add_exception_handler(RequestValidationError, validation_error_handler)

app.include_router(catalog_router)
app.include_router(quotes_router)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    """Liveness probe used by Docker Compose and the Fly.io health check."""
    return {"status": "ok", "environment": settings.environment}
