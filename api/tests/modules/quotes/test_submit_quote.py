"""``SubmitQuoteUseCase`` and ``SubmitEnquiryUseCase``, with no database and no HTTP.

This file is what the layering bought. Every collaborator the submission pipeline has is a
constructor argument -- the lead store, the catalog read, the rate limiter -- so all three are
fakes here and the suite runs with ``DATABASE_URL`` unset:

    uv run pytest tests/modules/quotes/test_submit_quote.py -q -p no:cacheprovider

The database-backed contract tests in ``test_quotes_api.py`` all stay. They are what proves the
wire shape did not move, and faster fakes cannot check that.
"""

from datetime import UTC, datetime

import pytest

from app.core.domain.interfaces import IRateLimiter, RateLimitVerdict
from app.modules.catalog.domain.enums import DisplayStyle, RuleRelation, SelectionMode
from app.modules.catalog.domain.models import Option, OptionGroup, OptionRule, Platform
from app.modules.quotes.application.dtos import (
    ContactInput,
    EnquiryCreateRequest,
    QuoteCreateRequest,
)
from app.modules.quotes.application.mappers import QuoteMapper
from app.modules.quotes.application.use_cases import (
    SubmitEnquiryUseCase,
    SubmitQuoteUseCase,
)
from app.modules.quotes.domain.enums import QuoteKind
from app.modules.quotes.domain.exceptions import (
    InvalidSelectionError,
    RateLimitedError,
    RejectedSubmissionError,
    UnknownPlatformError,
)
from app.modules.quotes.domain.filters import QuoteFilter
from app.modules.quotes.domain.interfaces import IQuoteRepository
from app.modules.quotes.domain.models import Quote


class FakeQuoteRepository(IQuoteRepository):
    """A dictionary with a ref generator. Stands in for Postgres, the commit and the retry."""

    def __init__(self) -> None:
        self.saved: list[Quote] = []

    def create(self, entity: Quote) -> Quote:
        # Everything Postgres would fill in: the key, the reference the unique index decides, and
        # the `now()` server default. A fake that left `created_at` unset would let a use case
        # that forgot to read one back pass here and fail in production.
        entity = entity.model_copy(
            update={
                "id": len(self.saved) + 1,
                "ref": f"TB-FAKE{len(self.saved)}",
                "created_at": datetime(2026, 8, 28, 9, 30, tzinfo=UTC),
            }
        )
        self.saved.append(entity)
        return entity

    def list(self, filters: QuoteFilter) -> list[Quote]:
        return list(self.saved)

    def by_ref(self, ref: str) -> Quote | None:
        return next((quote for quote in self.saved if quote.ref == ref), None)

    def count(self, filters: QuoteFilter) -> int:
        return len(self.saved)

    def update(self, entity: Quote) -> Quote:  # pragma: no cover - never called
        raise NotImplementedError

    def delete(self, entity: Quote) -> None:  # pragma: no cover - never called
        raise NotImplementedError


class FakePlatformRepository:
    """Only ``by_slug`` is reached from here; the rest of ``IPlatformRepository`` is not
    implemented rather than faked, so a use case that started reading the whole catalog would
    fail loudly instead of quietly passing."""

    def __init__(self, platform: Platform | None) -> None:
        self.platform = platform

    def by_slug(self, slug: str) -> Platform | None:
        if self.platform is not None and self.platform.slug == slug:
            return self.platform
        return None


class FakeLimiter(IRateLimiter):
    def __init__(self, allowed: bool = True, retry_after_seconds: int = 0) -> None:
        self.verdict = RateLimitVerdict(allowed=allowed, retry_after_seconds=retry_after_seconds)
        self.keys: list[str] = []

    def check(self, key: str) -> RateLimitVerdict:
        self.keys.append(key)
        return self.verdict


def _option(slug: str, name: str, delta: int = 0) -> Option:
    return Option(id=abs(hash(slug)) % 10_000, slug=slug, name=name, price_delta_cents=delta)


@pytest.fixture
def platform() -> Platform:
    """One platform with the three shapes the checks care about: a required single-select group,
    an optional multi-select one, and a rule between two of the options."""
    return Platform(
        id=1,
        slug="bristlecone",
        name="Bristlecone",
        purpose="expedition",
        chassis_basis="F-550",
        base_price_cents=21_450_000,
        option_groups=[
            OptionGroup(
                id=1,
                slug="cab",
                name="Cab",
                selection_mode=SelectionMode.single,
                required=True,
                display_style=DisplayStyle.card,
                options=[
                    _option("cab-regular", "Regular cab"),
                    _option("cab-crew", "Crew cab", 500_000),
                ],
            ),
            OptionGroup(
                id=2,
                slug="recovery",
                name="Recovery & Protection",
                selection_mode=SelectionMode.multi,
                required=False,
                display_style=DisplayStyle.card,
                options=[
                    _option("bumper-heavy", "Heavy front bumper", 220_000),
                    _option("winch-12000", "12,000 lb winch", 340_000),
                ],
            ),
        ],
        rules=[
            OptionRule(
                id=1,
                subject="winch-12000",
                relation=RuleRelation.requires,
                object="bumper-heavy",
            )
        ],
    )


def build_request(**overrides) -> QuoteCreateRequest:
    payload = {
        "platform_slug": "bristlecone",
        "option_slugs": ["cab-regular"],
        "contact": ContactInput(name="Dana Reyes", email="dana@example.com", phone=""),
        "elapsed_ms": 9_000,
    }
    payload.update(overrides)
    return QuoteCreateRequest(**payload)


def use_case(platform: Platform | None, **overrides) -> SubmitQuoteUseCase:
    deps = {
        "mapper": QuoteMapper(),
        "filter_class": QuoteFilter,
        "repository": FakeQuoteRepository(),
        "platforms": FakePlatformRepository(platform),
        "limiter": FakeLimiter(),
        "min_submit_ms": 2_500,
    }
    deps.update(overrides)
    return SubmitQuoteUseCase(**deps)


def test_a_valid_build_is_priced_and_stored(platform: Platform) -> None:
    submit = use_case(platform)

    lead = submit.exec(
        build_request(option_slugs=["cab-regular", "bumper-heavy", "winch-12000"]),
        "203.0.113.7",
    )

    assert lead.kind == QuoteKind.build
    assert lead.base_price_cents == 21_450_000
    assert lead.total_cents == 21_450_000 + 220_000 + 340_000
    assert [line.option_slug for line in lead.lines] == [
        "cab-regular",
        "bumper-heavy",
        "winch-12000",
    ]
    assert [line.group_name for line in lead.lines][1] == "Recovery & Protection"
    # The line carries the option's name and price as they were, not a pointer to the catalog.
    assert lead.lines[2].option_name == "12,000 lb winch"
    assert lead.lines[2].price_delta_cents == 340_000


def test_the_address_the_router_read_is_what_reaches_the_row_and_the_limiter(
    platform: Platform,
) -> None:
    limiter = FakeLimiter()
    repository = FakeQuoteRepository()
    submit = use_case(platform, limiter=limiter, repository=repository)

    submit.exec(build_request(), "198.51.100.4")

    assert limiter.keys == ["198.51.100.4"]
    assert repository.saved[0].source_ip == "198.51.100.4"


def test_a_filled_honeypot_is_rejected_before_anything_is_stored(platform: Platform) -> None:
    repository = FakeQuoteRepository()
    submit = use_case(platform, repository=repository)

    with pytest.raises(RejectedSubmissionError) as raised:
        submit.exec(build_request(website="https://cheap-pills.example"), "203.0.113.7")

    assert raised.value.status_code == 422
    assert raised.value.code == "rejected"
    # The message must not name the control that fired.
    assert "honeypot" not in raised.value.message.lower()
    assert repository.saved == []


def test_a_submission_faster_than_a_person_is_rejected(platform: Platform) -> None:
    with pytest.raises(RejectedSubmissionError):
        use_case(platform).exec(build_request(elapsed_ms=120), "203.0.113.7")


def test_a_missing_timing_is_not_held_against_the_submitter(platform: Platform) -> None:
    """A form submitted without JavaScript cannot report one."""
    assert use_case(platform).exec(build_request(elapsed_ms=None), "203.0.113.7").ref


def test_a_rate_limited_address_is_told_how_long_to_wait(platform: Platform) -> None:
    limiter = FakeLimiter(allowed=False, retry_after_seconds=42)

    with pytest.raises(RateLimitedError) as raised:
        use_case(platform, limiter=limiter).exec(build_request(), "203.0.113.7")

    assert raised.value.status_code == 429
    assert raised.value.headers == {"Retry-After": "42"}


def test_spam_screening_comes_before_the_rate_limit(platform: Platform) -> None:
    """Order, not just outcome: a submitter that fails both is told the vaguer of the two, and
    the limiter is never consulted for a request that was never a submission."""
    limiter = FakeLimiter(allowed=False, retry_after_seconds=42)

    with pytest.raises(RejectedSubmissionError):
        use_case(platform, limiter=limiter).exec(build_request(website="spam"), "203.0.113.7")

    assert limiter.keys == []


def test_an_unknown_platform_is_refused_before_the_selection_is_read() -> None:
    with pytest.raises(UnknownPlatformError) as raised:
        use_case(None).exec(build_request(option_slugs=["not-an-option"]), "203.0.113.7")

    assert raised.value.status_code == 404
    assert raised.value.code == "unknown_platform"
    assert raised.value.slug == "bristlecone"


def test_a_required_group_left_empty_is_a_structural_violation(platform: Platform) -> None:
    with pytest.raises(InvalidSelectionError) as raised:
        use_case(platform).exec(build_request(option_slugs=[]), "203.0.113.7")

    violation = raised.value.violations[0]
    assert violation.kind == "missing_required_group"
    assert violation.subject == "Cab"


def test_a_single_select_group_cannot_take_two_options(platform: Platform) -> None:
    with pytest.raises(InvalidSelectionError) as raised:
        use_case(platform).exec(
            build_request(option_slugs=["cab-regular", "cab-crew"]), "203.0.113.7"
        )

    assert {v.kind for v in raised.value.violations} == {"too_many_in_group"}


def test_an_unknown_option_is_reported_without_consulting_the_rules(platform: Platform) -> None:
    """Reporting both at once would explain a conflict with an option that does not exist."""
    with pytest.raises(InvalidSelectionError) as raised:
        use_case(platform).exec(
            build_request(option_slugs=["cab-regular", "winch-12000", "not-an-option"]),
            "203.0.113.7",
        )

    assert [v.kind for v in raised.value.violations] == ["unknown_option"]


def test_a_requires_rule_is_reported_with_names_a_person_would_recognise(
    platform: Platform,
) -> None:
    with pytest.raises(InvalidSelectionError) as raised:
        use_case(platform).exec(
            build_request(option_slugs=["cab-regular", "winch-12000"]), "203.0.113.7"
        )

    violation = raised.value.violations[0]
    assert violation.kind == "requires"
    assert violation.subject == "12,000 lb winch"
    assert violation.options == ("Heavy front bumper",)


def test_an_enquiry_is_stored_with_no_build_to_price(platform: Platform) -> None:
    submit = SubmitEnquiryUseCase(
        mapper=QuoteMapper(),
        filter_class=QuoteFilter,
        repository=FakeQuoteRepository(),
        platforms=FakePlatformRepository(platform),
        limiter=FakeLimiter(),
    )

    lead = submit.exec(
        EnquiryCreateRequest(
            platform_slug="bristlecone",
            contact=ContactInput(name="Sam Okafor", email="sam@example.com"),
            elapsed_ms=9_000,
        ),
        "203.0.113.7",
    )

    assert lead.kind == QuoteKind.enquiry
    # A named platform is an interest, not a build: it is recorded, and nothing is priced.
    assert lead.platform_name == "Bristlecone"
    assert lead.total_cents is None
    assert lead.base_price_cents is None
    assert lead.lines == []
