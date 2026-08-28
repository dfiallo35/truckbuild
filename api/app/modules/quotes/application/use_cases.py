"""Submitting a lead, as one class per shape of submission.

Nothing here names a ``Response``, a status code, a header or a session. What a caller cannot have
is raised as one of ``domain/exceptions.py``'s errors; two of those are rendered by the handler
``core`` installs and two by this module's router, and neither decision is made here.

``SubmitQuoteUseCase`` is the first thing in this service with a test that needs no Postgres --
``tests/modules/quotes/test_submit_quote.py`` runs it against a fake repository, a fake limiter
and a fake platform read. That is the whole return on the layering, stated as a test.
"""

import logging

from app.core.application.use_cases import CreateUseCase
from app.core.domain.interfaces import IRateLimiter
from app.modules.catalog.domain.interfaces import IPlatformRepository
from app.modules.catalog.domain.models import Platform
from app.modules.quotes.application.dtos import (
    LeadCreateRequest,
    QuoteCreateRequest,
    QuoteDetailOutput,
)
from app.modules.quotes.domain.exceptions import (
    InvalidSelectionError,
    RateLimitedError,
    RejectedSubmissionError,
    UnknownPlatformError,
)
from app.modules.quotes.domain.models import Quote
from app.modules.quotes.domain.selection import (
    SelectionViolation,
    rule_violations,
    structural_violations,
)
from app.modules.quotes.domain.spam import DEFAULT_MIN_ELAPSED_MS, screen

logger = logging.getLogger(__name__)


class SubmitLeadUseCase(CreateUseCase):
    """Screen it, look up whatever platform it names, judge it, store it.

    ``exec`` is overridden rather than only its hooks, which is the exception CLAUDE.md's rule
    allows for and worth stating the reason for: ``CreateUseCase.exec`` maps the request to an
    entity *before* ``validate`` runs, and a quote cannot be built before its selection has been
    judged -- pricing a selection that names an option the platform does not have raises. So the
    entity is built inside ``run``, and the order the template exists to fix,
    ``pre_run -> validate -> run -> post_run``, is exactly the order below.

    The three collaborators beyond the base's are constructor arguments rather than imports,
    which is what lets the test above substitute all three.
    """

    def __init__(
        self,
        *args,
        platforms: IPlatformRepository | None = None,
        limiter: IRateLimiter | None = None,
        min_submit_ms: int = DEFAULT_MIN_ELAPSED_MS,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.platforms = platforms
        self.limiter = limiter
        self.min_submit_ms = min_submit_ms

    def pre_run(self, create_request: LeadCreateRequest) -> Platform | None:
        """Load the platform, if one was named. Absence is *not* raised here: a submission that
        fails the spam controls must be refused as spam whether or not it also names a platform
        that no longer exists, and ``validate`` is where the order between those is decided."""
        if not create_request.platform_slug:
            return None
        return self.platforms.by_slug(create_request.platform_slug)

    def validate(
        self,
        create_request: LeadCreateRequest,
        platform: Platform | None,
        source_ip: str,
    ) -> None:
        verdict = screen(create_request.website, create_request.elapsed_ms, self.min_submit_ms)
        if verdict.automated:
            # Which control fired is logged and never sent: telling a submitter which check it
            # failed is telling it what to change.
            logger.warning("rejected submission from %s (%s)", source_ip, verdict.reason)
            raise RejectedSubmissionError(verdict.reason)

        limit = self.limiter.check(source_ip)
        if not limit.allowed:
            raise RateLimitedError(limit.retry_after_seconds)

        if create_request.platform_slug and platform is None:
            raise UnknownPlatformError(create_request.platform_slug)

    def run(
        self,
        create_request: LeadCreateRequest,
        platform: Platform | None,
        source_ip: str,
    ) -> Quote:
        entity = self.mapper.to_domain(create_request, platform, source_ip)
        return self.repository.create(entity)

    def post_run(self, create_request: LeadCreateRequest, created_entity: Quote) -> Quote:
        return created_entity

    def exec(self, create_request: LeadCreateRequest, source_ip: str = "") -> QuoteDetailOutput:
        """``source_ip`` is an argument rather than a field on the request because it is not part
        of the body: the router reads it from the forwarded header, so no client can name its
        own. Reading that header is HTTP and stays in the router; a use case is handed an
        address."""
        platform = self.pre_run(create_request=create_request)
        self.validate(create_request=create_request, platform=platform, source_ip=source_ip)
        quote = self.run(create_request=create_request, platform=platform, source_ip=source_ip)
        quote = self.post_run(create_request=create_request, created_entity=quote)
        return self.get_output(quote)


class SubmitQuoteUseCase(SubmitLeadUseCase):
    """A configured build. ``POST /v1/quotes``."""

    def validate(
        self,
        create_request: QuoteCreateRequest,
        platform: Platform | None,
        source_ip: str,
    ) -> None:
        super().validate(create_request=create_request, platform=platform, source_ip=source_ip)

        violations: list[SelectionViolation] = structural_violations(
            platform, create_request.option_slugs
        )
        if not violations:
            # Compatibility rules are only meaningful once every slug is real; reporting both at
            # once would explain a conflict between an option and one that does not exist.
            violations = rule_violations(platform, create_request.option_slugs)
        if violations:
            raise InvalidSelectionError(violations)

    def post_run(self, create_request: QuoteCreateRequest, created_entity: Quote) -> Quote:
        logger.info(
            "stored quote %s for %s at %s",
            created_entity.ref,
            created_entity.platform_slug,
            created_entity.total_cents,
        )
        return created_entity


class SubmitEnquiryUseCase(SubmitLeadUseCase):
    """The /contact form. ``POST /v1/enquiries``.

    The same pipeline with no build to price: same storage, same mail, same spam controls, so
    sales reads one list rather than two. A platform may be named as an interest, and is looked
    up and rejected if unknown for the same reason a build's is -- but nothing is priced.
    """

    def post_run(self, create_request: LeadCreateRequest, created_entity: Quote) -> Quote:
        logger.info("stored enquiry %s", created_entity.ref)
        return created_entity
