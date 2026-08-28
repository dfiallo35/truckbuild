"""Rendering every rejection into the one error body.

The body itself -- ``FieldError`` and ``ErrorBody`` -- is in ``core/application/dtos.py``,
because it is the wire contract and a use case may need to build one. Everything here turns one
into an HTTP response, which is a framework's job and stays on this side of the line.

Three handlers, because there are three ways this API says no. ``BaseError`` is what domain and
application code raises; FastAPI's own 422 and Starlette's ``HTTPException`` are reshaped into
the same envelope so the web app has a single body to parse and render beside the field at
fault, whatever produced it.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.application.dtos import ErrorBody, FieldError
from app.core.domain.exceptions import BaseError


def error_response(
    status_code: int,
    code: str,
    message: str,
    errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorBody(code=code, message=message, errors=errors or [])
    return JSONResponse(status_code=status_code, content=payload.model_dump(), headers=headers)


def _field_path(loc: tuple[int | str, ...]) -> str | None:
    """``("body", "contact", "email")`` -> ``"contact.email"``.

    The leading ``body``/``query`` marker is dropped: the client knows where it put the value,
    and the form field it needs to highlight is named by the rest.
    """
    parts = [str(part) for part in loc if part not in ("body", "query", "path")]
    return ".".join(parts) if parts else None


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        status_code=422,
        code="validation_error",
        message="Some details need another look.",
        errors=[
            FieldError(field=_field_path(error["loc"]), message=error["msg"], code=error["type"])
            for error in exc.errors()
        ],
    )


# ``raise HTTPException(404, "...")`` is the idiomatic way to reject from inside a dependency,
# which is how the admin guard has to work -- a dependency cannot return a response. These names
# keep such a rejection carrying the same machine-readable ``code`` as one raised by hand.
_CODES = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    502: "bad_gateway",
}


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Reshape ``{"detail": ...}`` into the one error body. Registered for Starlette's own
    exception too, so a request for a route that does not exist answers in the same shape as a
    request for a platform that does not."""
    return error_response(
        status_code=exc.status_code,
        code=_CODES.get(exc.status_code, "error"),
        message=str(exc.detail),
        headers=dict(exc.headers) if exc.headers else None,
    )


async def base_error_handler(_: Request, exc: BaseError) -> JSONResponse:
    """A domain error, in the same envelope as everything else.

    This is what lets ``domain`` and ``application`` raise ``NotFoundError`` instead of importing
    ``HTTPException``: the status and the machine-readable code ride on the exception, and the
    decision to express them over HTTP is made here and nowhere else.
    """
    return error_response(status_code=exc.status_code, code=exc.code, message=exc.message)
