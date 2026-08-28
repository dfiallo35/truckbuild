"""The assembly: everything that is true of the app regardless of which routes it carries.

``app/main.py`` is left with the one thing that is *not* generic -- which routers exist and in
what order -- so that the middleware order, the exception handlers and the CORS policy are stated
once, here, rather than re-derived by whoever adds the next entrypoint.

``app.main:app`` remains the ASGI path: ``vercel.json``, the Dockerfile and ``docker compose``
all name it, so it is a public identifier of this service in the same sense a slug is.
"""

import logging

from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from app.core.config import Settings
from app.core.domain.exceptions import BaseError
from app.core.presentation.errors import (
    base_error_handler,
    http_error_handler,
    validation_error_handler,
)
from app.core.presentation.telemetry import install as install_telemetry


def create_app(
    *,
    title: str,
    version: str,
    description: str,
    router: APIRouter,
    settings: Settings,
) -> FastAPI:
    # Uvicorn configures its own loggers and nothing else, so without this the application's own
    # INFO lines -- the stored-quote records and, in development, the mail the mailer would have
    # sent -- go nowhere at all.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    app = FastAPI(title=title, version=version, description=description)

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

    # Structured request logs always; Sentry only when a DSN is configured. Added last on
    # purpose: `add_middleware` inserts at position 0 and the stack is built by wrapping in
    # reverse, so the last one added is the outermost. Telemetry wants to be outermost -- it
    # stamps the request id before anything else can fail, and it sees the response every other
    # layer produced.
    install_telemetry(app, settings)

    # Every rejection leaves this API in one shape, FastAPI's own 422 included -- see
    # app/core/presentation/errors.py.
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(BaseError, base_error_handler)

    app.include_router(router)
    return app
