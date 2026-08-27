"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from app.config import get_settings
from app.errors import http_error_handler, validation_error_handler
from app.routers.admin import router as admin_router
from app.routers.catalog import router as catalog_router
from app.routers.quotes import router as quotes_router
from app.services.telemetry import install as install_telemetry

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
    # The web app forwards its request id on the hop into this service, and reads it back off
    # the response so a browser-side failure and an API-side one share an identifier. Without
    # this the header is set but unreadable from a browser.
    expose_headers=["X-Request-ID"],
)

# Structured request logs always; Sentry only when a DSN is configured. Added last on purpose:
# `add_middleware` inserts at position 0 and the stack is built by wrapping in reverse, so the
# last one added is the outermost. Telemetry wants to be outermost -- it stamps the request id
# before anything else can fail, and it sees the response every other layer produced.
install_telemetry(app, settings)

# Every rejection leaves this API in one shape, FastAPI's own 422 included, so the web app
# has a single error body to parse and render beside the field at fault. See app/errors.py.
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)

app.include_router(catalog_router)
app.include_router(quotes_router)
app.include_router(admin_router)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    """Liveness probe used by Docker Compose and the host's health check.

    Also the way to wake a sleeping free-tier instance before a deploy that needs it -- see
    docs/deploy.md."""
    return {"status": "ok", "environment": settings.environment}
