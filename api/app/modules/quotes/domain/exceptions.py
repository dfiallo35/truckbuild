"""Errors lead submission raises when it cannot accept what it was given.

Nothing under ``domain/`` or ``application/`` imports a web framework or names
``HTTPException``. What a rejection *is* -- its status, its machine-readable ``code``, any header
the answer needs -- rides on the exception, which is the kernel's own mechanism (see
``core/domain/exceptions.py``); the decision to express it over HTTP is made at the edge.

Two of the four are rendered by the handler ``core/presentation/errors.py`` installs and need
nothing from this module's router. The other two carry an ``errors[]`` array whose sentences name
options and groups by the words a customer would read -- that prose is presentation's, so
``presentation/quotes_api.py`` renders those two itself. What it does *not* decide is the status,
the code or the headline: those are here.
"""

from app.core.domain.exceptions import BaseError, NotFoundError
from app.modules.quotes.domain.selection import SelectionViolation

# Deliberately vague: naming the control that fired tells an automated submitter what to change.
REJECTED_MESSAGE = "We couldn't accept this submission. Please email us directly."

RATE_LIMITED_MESSAGE = (
    "That's a lot of submissions in a short time. Try again shortly, or email us."
)


class RejectedSubmissionError(BaseError):
    """A spam control fired. ``reason`` names which one, for the log only."""

    status_code = 422
    code = "rejected"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(REJECTED_MESSAGE)


class RateLimitedError(BaseError):
    """Too many submissions from one address.

    ``Retry-After`` rides on the exception as a header rather than being re-derived at the edge:
    how long to wait is the limiter's answer, and by the time the handler sees this the limiter
    is long out of scope.
    """

    status_code = 429
    code = "rate_limited"

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(RATE_LIMITED_MESSAGE, headers={"Retry-After": str(retry_after_seconds)})


class InvalidSelectionError(BaseError):
    """The build is not one this platform can be ordered as.

    Carries the violations rather than a rendered body: what is wrong with a selection is a fact
    about the catalog, and the sentence a customer reads about it is not.
    """

    status_code = 422
    code = "invalid_selection"

    def __init__(self, violations: list[SelectionViolation]) -> None:
        self.violations = tuple(violations)
        super().__init__("This build needs a change.")


class UnknownPlatformError(NotFoundError):
    """The submission names a platform that is not in the catalog.

    ``unknown_platform`` rather than the inherited ``not_found`` so the web app can tell "the
    build URL you shared names a platform that no longer exists" apart from "that route does not
    exist" -- the same code ``GET /v1/platforms/{slug}`` answers with for the same cause.
    """

    code = "unknown_platform"

    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__("That platform no longer exists.")


class QuoteNotFoundError(NotFoundError):
    """No lead with that reference. Raised by the lookup behind the admin detail endpoint."""

    def __init__(self, ref: str) -> None:
        self.ref = ref
        super().__init__(f"no quote with reference {ref!r}")
