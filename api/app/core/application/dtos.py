"""The shapes crossing the application boundary: what a use case is asked for, and what it
answers with.

Distinct from ``domain/models.py`` on purpose. An entity is a fact; a DTO is a message. They look
alike on the day a feature is written and diverge the first time the wire needs a field the
domain does not have (or, more often, must stop sending one it does).

Pure pydantic -- no ``fastapi``, no ``sqlmodel``. The error body below is the one exception worth
naming: it *is* the wire contract, shared by every rejection this API makes, and it lives here
rather than in ``presentation`` so a use case can build one without importing a web framework.
``error_response``, which turns it into an HTTP response, is in ``core/presentation/errors.py``
where the framework belongs.
"""

from pydantic import BaseModel


class BaseCreateRequest(BaseModel):
    """What a ``CreateUseCase`` is given. Mapped to an entity by the feature's mapper."""


class BaseUpdateRequest(BaseModel):
    """A partial edit. Applied to an existing entity by ``BaseMapper.to_update``."""


class BaseBatchUpdateRequest(BaseModel):
    items: list[BaseUpdateRequest]


class BaseOutput(BaseModel):
    """What a use case answers with. A router serializes one; it does not build one."""


class BasePaginatedOutput[PaginatedItemOutput: BaseOutput](BaseModel):
    """A page of results plus the window it was taken from.

    ``limit``/``offset`` rather than ``page``/``size``/``pages``, because that is what
    ``GET /v1/admin/quotes`` already answers with and what the admin page already reads.

    Both windows are optional here for the same reason they are optional on ``BaseFilter``:
    core has no opinion about page size. A feature whose endpoint always has one narrows them
    to ``int`` in its own subclass, which is a stricter schema over an identical body.
    """

    items: list[PaginatedItemOutput]
    total: int
    limit: int | None = None
    offset: int | None = None


class FieldError(BaseModel):
    """``field`` is a dotted path into the submitted body (``contact.email``), or ``None`` for a
    failure that belongs to the submission as a whole."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorBody(BaseModel):
    """One error shape for the whole API.

    Every rejection -- a malformed body, a broken option combination, a rate limit -- comes back
    as ``{code, message, errors[]}`` with ``errors[].field`` naming the input at fault. The web
    app renders those beside the field they belong to, and it can only do that if there is a
    single shape to parse rather than one per failure mode.
    """

    code: str
    message: str
    errors: list[FieldError] = []
