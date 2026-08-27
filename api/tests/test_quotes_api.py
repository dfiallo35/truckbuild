"""Contract tests for the lead endpoints, run against the seeded Postgres database (migrate,
seed, then run this suite -- same setup as tests/test_catalog_api.py).

The one these exist for: the total stored is the server's, computed from the option slugs, no
matter what the browser says it should be.
"""

import itertools

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import Quote, QuoteKind
from app.routers.quotes import limiter

client = TestClient(app)

BASE_PRICE_CENTS = 21_450_000
# The first option of every required group -- what the configurator opens on.
DEFAULT_SELECTION = [
    "cab-regular",
    "shell-standard",
    "galley-compact",
    "suspension-standard",
    "finish-satin-black",
]

_ips = itertools.count(1)


@pytest.fixture(autouse=True)
def _fresh_limiter() -> None:
    """The limiter is process-global, so one test's submissions would otherwise count against
    the next one's."""
    limiter.reset()


@pytest.fixture
def ip() -> str:
    """A distinct forwarded address per test, for the same reason."""
    return f"203.0.113.{next(_ips) % 250 + 1}"


def submit(payload: dict, ip: str, path: str = "/v1/quotes"):
    return client.post(path, json=payload, headers={"x-forwarded-for": ip})


def build_payload(**overrides) -> dict:
    payload = {
        "platform_slug": "bristlecone",
        "option_slugs": list(DEFAULT_SELECTION),
        "contact": {"name": "Dana Reyes", "email": "dana@example.com", "phone": "+1 555 0100"},
        "intended_use": "Two-up desert travel, three weeks at a time.",
        "timeline": "3–6 months",
        "notes": "",
        "website": "",
        "elapsed_ms": 9_000,
    }
    payload.update(overrides)
    return payload


def stored(ref: str) -> Quote:
    with Session(engine) as session:
        quote = session.exec(select(Quote).where(Quote.ref == ref)).one()
        # Touch the lines inside the session; they are lazy-loaded.
        len(quote.lines)
        return quote


def test_a_valid_build_is_stored_and_priced_by_the_server(ip: str) -> None:
    response = submit(
        build_payload(option_slugs=[*DEFAULT_SELECTION, "bumper-heavy", "winch-12000"]), ip
    )
    assert response.status_code == 201, response.text

    body = response.json()
    expected = BASE_PRICE_CENTS + 220_000 + 340_000
    assert body["total_cents"] == expected
    assert body["base_price_cents"] == BASE_PRICE_CENTS
    assert body["kind"] == "build"
    assert body["ref"].startswith("TB-")

    quote = stored(body["ref"])
    assert quote.total_cents == expected
    assert quote.contact_email == "dana@example.com"
    assert {line.option_slug for line in quote.lines} >= {"winch-12000", "bumper-heavy"}
    assert next(line for line in quote.lines if line.option_slug == "winch-12000").group_name


def test_a_client_supplied_total_is_ignored(ip: str) -> None:
    """The checkpoint case: a browser-sent price is user input, not a fact."""
    response = submit(build_payload(total_cents=1, base_price_cents=1), ip)
    assert response.status_code == 201, response.text
    assert response.json()["total_cents"] == BASE_PRICE_CENTS
    assert stored(response.json()["ref"]).total_cents == BASE_PRICE_CENTS


def test_a_requires_rule_is_enforced_server_side(ip: str) -> None:
    response = submit(build_payload(option_slugs=[*DEFAULT_SELECTION, "winch-12000"]), ip)
    assert response.status_code == 422

    body = response.json()
    assert body["code"] == "invalid_selection"
    assert [error["code"] for error in body["errors"]] == ["requires"]
    assert "bumper" in body["errors"][0]["message"].lower()
    assert body["errors"][0]["field"] == "option_slugs"


def test_an_excludes_rule_is_enforced_server_side(ip: str) -> None:
    response = submit(
        build_payload(option_slugs=[*DEFAULT_SELECTION, "rooftop-tent", "solar-max"]), ip
    )
    assert response.status_code == 422
    body = response.json()
    assert [error["code"] for error in body["errors"]] == ["excludes"]
    assert "cannot be fitted" in body["errors"][0]["message"]


def test_a_required_group_cannot_be_left_empty(ip: str) -> None:
    without_finish = [slug for slug in DEFAULT_SELECTION if slug != "finish-satin-black"]
    response = submit(build_payload(option_slugs=without_finish), ip)
    assert response.status_code == 422
    assert "missing_required_group" in {error["code"] for error in response.json()["errors"]}


def test_a_single_select_group_cannot_take_two_options(ip: str) -> None:
    response = submit(build_payload(option_slugs=[*DEFAULT_SELECTION, "cab-crew"]), ip)
    assert response.status_code == 422
    assert "too_many_in_group" in {error["code"] for error in response.json()["errors"]}


def test_an_option_from_another_platform_is_rejected(ip: str) -> None:
    response = submit(build_payload(option_slugs=[*DEFAULT_SELECTION, "not-an-option"]), ip)
    assert response.status_code == 422
    assert "unknown_option" in {error["code"] for error in response.json()["errors"]}


def test_an_unknown_platform_is_404(ip: str) -> None:
    response = submit(build_payload(platform_slug="not-a-real-platform"), ip)
    assert response.status_code == 404
    assert response.json()["code"] == "unknown_platform"


def test_a_malformed_body_comes_back_in_the_same_error_shape(ip: str) -> None:
    """FastAPI's own 422 is reshaped so the web app has one body to parse -- see app/errors.py."""
    response = submit(build_payload(contact={"name": "Dana", "email": "not-an-email"}), ip)
    assert response.status_code == 422

    body = response.json()
    assert body["code"] == "validation_error"
    assert "contact.email" in {error["field"] for error in body["errors"]}


def test_a_filled_honeypot_is_rejected_and_stores_nothing(ip: str) -> None:
    response = submit(build_payload(website="https://cheap-pills.example"), ip)
    assert response.status_code == 422
    assert response.json()["code"] == "rejected"
    # The message must not name the control that fired.
    assert "honeypot" not in response.text.lower()

    with Session(engine) as session:
        assert session.exec(select(Quote).where(Quote.source_ip == ip)).first() is None


def test_a_submission_faster_than_a_person_is_rejected(ip: str) -> None:
    response = submit(build_payload(elapsed_ms=120), ip)
    assert response.status_code == 422
    assert response.json()["code"] == "rejected"


def test_a_missing_timing_is_not_held_against_the_submitter(ip: str) -> None:
    """A form submitted without JavaScript cannot report one."""
    response = submit(build_payload(elapsed_ms=None), ip)
    assert response.status_code == 201


def test_repeated_submissions_from_one_address_are_rate_limited(ip: str) -> None:
    statuses = [submit(build_payload(), ip).status_code for _ in range(7)]
    assert statuses[:5] == [201] * 5
    assert statuses[5:] == [429, 429]

    limited = submit(build_payload(), ip)
    assert limited.json()["code"] == "rate_limited"
    assert int(limited.headers["retry-after"]) > 0


def test_another_address_is_unaffected_by_someone_elses_limit(ip: str) -> None:
    for _ in range(6):
        submit(build_payload(), ip)
    assert submit(build_payload(), "198.51.100.7").status_code == 201


def test_an_enquiry_is_stored_without_a_build(ip: str) -> None:
    response = submit(
        {
            "contact": {"name": "Sam Okafor", "email": "sam@example.com", "phone": ""},
            "intended_use": "Fleet of four, mixed duty.",
            "timeline": "1–3 months",
            "website": "",
            "elapsed_ms": 9_000,
        },
        ip,
        path="/v1/enquiries",
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["kind"] == "enquiry"
    assert body["total_cents"] is None
    assert body["lines"] == []

    quote = stored(body["ref"])
    assert quote.kind == QuoteKind.enquiry
    assert quote.platform_slug is None


def test_an_enquiry_can_name_a_platform_of_interest(ip: str) -> None:
    response = submit(
        {
            "platform_slug": "ironwood",
            "contact": {"name": "Sam Okafor", "email": "sam@example.com"},
            "elapsed_ms": 9_000,
        },
        ip,
        path="/v1/enquiries",
    )
    assert response.status_code == 201, response.text
    assert response.json()["platform_name"] == "Ironwood"


def test_an_enquiry_naming_an_unknown_platform_is_404(ip: str) -> None:
    response = submit(
        {
            "platform_slug": "not-a-real-platform",
            "contact": {"name": "Sam Okafor", "email": "sam@example.com"},
            "elapsed_ms": 9_000,
        },
        ip,
        path="/v1/enquiries",
    )
    assert response.status_code == 404


def test_a_broken_mail_provider_still_leaves_the_lead_saved(ip: str, monkeypatch) -> None:
    """The stage 5 'done when': mail is best-effort, the row is not."""

    class BrokenClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> "BrokenClient":
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, *args, **kwargs):
            raise RuntimeError("mail provider is down")

    from app.services import mailer

    monkeypatch.setattr(mailer.httpx, "AsyncClient", BrokenClient)
    monkeypatch.setattr(mailer, "TIMEOUT_SECONDS", 0.1)

    settings = app.dependency_overrides
    from app.config import get_settings

    broken = get_settings().model_copy(update={"resend_api_key": "re_broken_key"})
    settings[get_settings] = lambda: broken
    try:
        response = submit(build_payload(), ip)
    finally:
        settings.pop(get_settings, None)

    assert response.status_code == 201
    assert stored(response.json()["ref"]).total_cents == BASE_PRICE_CENTS
