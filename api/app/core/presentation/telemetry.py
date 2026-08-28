"""Analytics and error tracking for the API.

Two layers, deliberately separable:

- **Structured request logs, always on.** One JSON line per request carrying method, path,
  status, duration and a request id. The host ingests stdout and indexes it, so this is a real
  analytics and debugging surface with no vendor attached and nothing to configure. It is also
  the layer that survives Sentry being switched off, misconfigured, or rate-limited.
- **Sentry, on only when ``SENTRY_DSN`` is set.** ``sentry_sdk.init`` with no DSN is inert, so
  the import and the call are unconditional and the *behaviour* is not. That keeps development
  and CI free of a network dependency while leaving production one environment variable away
  from full tracing.

The request id is the seam between them and the point of the whole module: a 500 in Sentry, a
line in the host's log view, and the ``X-Request-ID`` header the caller saw all carry the same
value, so a customer saying "it failed at about ten past" is a lookup, not an investigation.
"""

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import sentry_sdk
from fastapi import FastAPI, Request, Response
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings

logger = logging.getLogger("app.telemetry")

REQUEST_ID_HEADER = "X-Request-ID"

# Paths whose every hit would drown the useful lines. The platform polls the health check
# every few seconds; logging that says nothing except that the platform is still running.
_QUIET_PATHS = frozenset({"/healthz"})


def _scrub(event: dict, _hint: dict) -> dict | None:
    """Keep lead data out of the error tracker.

    Quote submissions carry a name, an email and a phone number. An exception raised while
    handling one should report *that it happened*, not ship the customer's contact details to
    a third party -- especially when the privacy page promises otherwise.
    """
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            for name in list(headers):
                if name.lower() in {"authorization", "cookie", "x-admin-token"}:
                    headers[name] = "[redacted]"
    return event


class RequestLogMiddleware(BaseHTTPMiddleware):
    """One structured line per request, and a request id on the way back out."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # An id supplied by the caller wins, so a trace started in the web app keeps its
        # identity across the hop into this service rather than being renamed halfway.
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        sentry_sdk.set_tag("request_id", request_id)

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Logged here so the failure is on stdout with its request id even if Sentry is
            # off; re-raised so Sentry's own middleware and FastAPI's handlers still see it.
            duration_ms = (time.perf_counter() - started) * 1000
            logger.error(
                json.dumps(
                    {
                        "event": "request.failed",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(duration_ms, 1),
                    }
                )
            )
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id

        if request.url.path not in _QUIET_PATHS:
            logger.info(
                json.dumps(
                    {
                        "event": "request",
                        "request_id": request_id,
                        "method": request.method,
                        # The routed template (`/v1/platforms/{slug}`) rather than the concrete
                        # path, so the lines group into endpoints instead of one bucket per
                        # slug. Falls back to the raw path for a 404, which has no route.
                        "route": getattr(request.scope.get("route"), "path", request.url.path),
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": round(duration_ms, 1),
                    }
                )
            )

        return response


def install(app: FastAPI, settings: Settings) -> None:
    """Wire telemetry into the app. Safe to call with no DSN configured."""
    sentry_sdk.init(
        dsn=settings.sentry_dsn,  # None disables the SDK entirely.
        environment=settings.environment,
        release=settings.release,
        # Full tracing on a marketing-site API is affordable and the traffic is low; drop this
        # if the plan's quota ever becomes the constraint.
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # The catalog is public, but a quote body is not -- see _scrub.
        send_default_pii=False,
        before_send=_scrub,
        integrations=[StarletteIntegration(), FastApiIntegration()],
    )

    app.add_middleware(RequestLogMiddleware)
