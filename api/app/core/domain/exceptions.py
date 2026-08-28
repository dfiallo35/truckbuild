"""Domain errors: what code raises when it cannot do what was asked.

The point of these is that nothing in ``domain/`` or ``application/`` ever names
``HTTPException`` again. A use case that raises ``NotFoundError`` can be tested without a web
framework and reused behind something that is not HTTP; ``core/presentation/errors.py`` is the
one place that decides such an error renders as ``{code, message, errors[]}`` with a status.

Each carries a stable machine-readable ``code``, which is what the web app switches on. Messages
are literal English: the reference repository renders every message through a Spanish/English
catalog, and docs/decisions.md defers i18n explicitly.
"""


class BaseError(Exception):
    """Base for every error this service raises deliberately.

    ``status_code`` is carried on the exception rather than chosen by the handler so that a use
    case saying "this is a 409" does not have to be re-derived from the exception's type at the
    edge, where the reason has been lost.
    """

    status_code: int = 500
    code: str = "error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        super().__init__(message)


class NotFoundError(BaseError):
    """Nothing matched. Subclassed per feature so the message can name what was looked for."""

    status_code = 404
    code = "not_found"


class NotValidOrderByError(BaseError):
    """``order_by`` named a column the table does not have.

    Rejected rather than ignored: a silently dropped sort is a page that looks right, is in the
    wrong order, and gives nobody a reason to look.
    """

    status_code = 400
    code = "invalid_order_by"

    def __init__(self, order_by: str, table_name: str) -> None:
        super().__init__(f"{table_name!r} cannot be ordered by {order_by!r}.")
