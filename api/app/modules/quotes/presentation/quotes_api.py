"""Lead submission: a configured build (``POST /v1/quotes``) or a general enquiry
(``POST /v1/enquiries``).

Each handler does three things and nothing else: read the caller's address off the request, call
one use case, and render what comes back. The spam screening, the rate limit, the catalog lookup,
the selection checks, the pricing, the aggregate, the commit and its retry all left in Stage 11 --
see ``application/use_cases.py`` and ``infrastructure/postgres/repositories.py``.

Three rules keep the rest here rather than one layer down:

- **The server price is the only price.** The request body has no field for a total, and the
  selection is re-validated against the live catalog before anything is stored. What the browser
  computed for the price bar is a UX affordance; what is stored is computed by the use case.
- **A saved lead beats a perfect response.** Once the row is committed the request has succeeded.
  Mail goes out in a ``BackgroundTasks`` job that swallows its own failures, because a lead lost
  to a mail outage is the expensive failure, not a missing confirmation email. Scheduling is a
  framework capability: the use case returns what needs sending, and this layer decides when.
- **The wording a customer reads lives where the wording lives.** Two of this module's rejections
  carry an ``errors[]`` array naming options and groups in the words a person would recognise, so
  they are rendered here from the violations the domain reported. Their status, code and headline
  still come off the exception; ``rejected`` and ``rate_limited`` carry no such array and are
  rendered by the handler ``core`` installs, with no code here at all.
"""

from typing import Annotated

from fastapi import BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse

from app.core.application.dtos import FieldError
from app.core.presentation.errors import error_response
from app.modules.catalog.domain.interfaces import IPlatformRepository
from app.modules.quotes.application.dtos import (
    EnquiryCreateRequest,
    QuoteCreateRequest,
    QuoteOutput,
)
from app.modules.quotes.application.interfaces import IMailer
from app.modules.quotes.application.services import QuoteService
from app.modules.quotes.domain.exceptions import InvalidSelectionError, UnknownPlatformError
from app.modules.quotes.domain.selection import SelectionViolation, SelectionViolationKind


def get_quote_service() -> QuoteService:  # pragma: no cover - bound in app/main.py
    """The service this module answers with, bound at the composition root.

    A router may not name an adapter -- ``presentation`` and ``infrastructure`` are sibling layers
    that cannot see each other -- so it declares what it needs and ``app/main.py`` fills it from
    ``app/modules/quotes/dependencies.py``. An unbound port fails loudly on the first request
    rather than quietly returning nothing; ``tests/test_composition_root.py`` fails before that.
    """
    raise NotImplementedError("get_quote_service is bound at the composition root in app/main.py")


def get_mailer() -> IMailer:  # pragma: no cover - bound in app/main.py
    """The mailer the background task is scheduled against. Injected rather than imported for the
    same reason as the service, and so a test can substitute one that records instead of sends."""
    raise NotImplementedError("get_mailer is bound at the composition root in app/main.py")


def get_platform_repository() -> IPlatformRepository:  # pragma: no cover - bound in app/main.py
    """The port this module reads the catalog through, bound at the composition root.

    ``quotes`` may name ``catalog``'s ``domain`` and ``application`` and never its adapters (the
    facade rule, CLAUDE.md), so it declares what it needs and ``app/main.py`` -- which is allowed
    to know how the application is assembled -- binds it to
    ``app/modules/catalog/dependencies.py``. Declared here rather than in this module's
    ``dependencies.py``, which consumes it, because a port is something a *layer* cannot fill and
    this is where they are discovered from.
    """
    raise NotImplementedError(
        "get_platform_repository is bound at the composition root in app/main.py"
    )


QuoteServiceDep = Annotated[QuoteService, Depends(get_quote_service)]
MailerDep = Annotated[IMailer, Depends(get_mailer)]


def _client_ip(request: Request) -> str:
    """The visitor's address, not the web app's.

    The browser never reaches this API directly (see CLAUDE.md) -- every submission arrives from
    the Next.js server action, so without the forwarded header every visitor in the world would
    share one rate-limit bucket. Trusting the header is safe precisely because that proxy is the
    only way in; if this API is ever exposed publicly, the socket peer becomes the honest key.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _sentence(violation: SelectionViolation) -> str:
    """One violation, as the sentence a customer reads.

    The domain reported *what* is wrong, with the nouns already resolved to display names. Only
    the wording is decided here, beside the rest of this API's wording.
    """
    joined = ", ".join(violation.options)
    match violation.kind:
        case SelectionViolationKind.unknown_option:
            return f"{violation.subject} has no option {joined}."
        case SelectionViolationKind.duplicate_option:
            return f"Listed more than once: {joined}."
        case SelectionViolationKind.too_many_in_group:
            return f"{violation.subject} takes one choice, not {len(violation.options)}."
        case SelectionViolationKind.missing_required_group:
            return f"{violation.subject} needs a choice."
        case "requires":
            return f"{violation.subject} needs the {joined}."
        case _:
            return f"{violation.subject} cannot be fitted with the {joined}."


def _invalid_selection(error: InvalidSelectionError) -> JSONResponse:
    return error_response(
        error.status_code,
        error.code,
        error.message,
        [
            FieldError(field="option_slugs", code=violation.kind, message=_sentence(violation))
            for violation in error.violations
        ],
    )


def _unknown_platform(error: UnknownPlatformError) -> JSONResponse:
    return error_response(
        error.status_code,
        error.code,
        error.message,
        [FieldError(field="platform_slug", message=f"No platform {error.slug!r}.")],
    )


def create_quote(
    payload: QuoteCreateRequest,
    request: Request,
    background: BackgroundTasks,
    service: QuoteServiceDep,
    mailer: MailerDep,
) -> QuoteOutput | JSONResponse:
    try:
        lead = service.submit_quote(payload, _client_ip(request))
    except InvalidSelectionError as error:
        return _invalid_selection(error)
    except UnknownPlatformError as error:
        return _unknown_platform(error)

    background.add_task(mailer.send_lead_emails, lead)
    return QuoteOutput.of(lead)


def create_enquiry(
    payload: EnquiryCreateRequest,
    request: Request,
    background: BackgroundTasks,
    service: QuoteServiceDep,
    mailer: MailerDep,
) -> QuoteOutput | JSONResponse:
    """The /contact form. Same storage, same mail, same spam controls -- there is just no build
    to price, so sales reads one list rather than two."""
    try:
        lead = service.submit_enquiry(payload, _client_ip(request))
    except UnknownPlatformError as error:
        return _unknown_platform(error)

    background.add_task(mailer.send_lead_emails, lead)
    return QuoteOutput.of(lead)
