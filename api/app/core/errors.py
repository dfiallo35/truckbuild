"""One error shape for the whole API.

Every rejection -- a malformed body, a broken option combination, a rate limit -- comes back as
``{code, message, errors[]}`` with ``errors[].field`` naming the input at fault. The web app
renders those beside the field they belong to, and it can only do that if there is a single
shape to parse rather than one per failure mode. FastAPI's own 422 body is reshaped into this
by ``validation_error_handler``, and its ``{"detail": ...}`` body by ``http_error_handler``, for
the same reason.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException


class FieldError(BaseModel):
    """``field`` is a dotted path into the submitted body (``contact.email``), or ``None`` for a
    failure that belongs to the submission as a whole."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorOut(BaseModel):
    code: str
    message: str
    errors: list[FieldError] = []


def error_response(
    status_code: int,
    code: str,
    message: str,
    errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorOut(code=code, message=message, errors=errors or [])
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
