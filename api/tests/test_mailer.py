"""The mailer's two contracts: the summary sales reads is complete, and nothing it does can
fail the request that triggered it."""

from datetime import UTC, datetime

import pytest

from app.config import Settings
from app.models.enums import QuoteKind
from app.schemas.quote import ContactIn, QuoteDetail, QuoteLineOut
from app.services import mailer


@pytest.fixture
def detail() -> QuoteDetail:
    return QuoteDetail(
        ref="TB-K7MQ4C",
        kind=QuoteKind.build,
        platform_slug="bristlecone",
        platform_name="Bristlecone",
        base_price_cents=21_450_000,
        total_cents=22_010_000,
        lines=[
            QuoteLineOut(
                group_name="Recovery & Protection",
                option_slug="bumper-heavy",
                option_name="Heavy front bumper",
                price_delta_cents=220_000,
            ),
            QuoteLineOut(
                group_name="Recovery & Protection",
                option_slug="winch-12000",
                option_name="12,000 lb winch",
                price_delta_cents=340_000,
            ),
        ],
        created_at=datetime(2026, 8, 27, 9, 30, tzinfo=UTC),
        contact=ContactIn(name="Dana Reyes", email="dana@example.com", phone="+1 555 0100"),
        intended_use="Two-up desert travel.",
        timeline="3–6 months",
        notes="",
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(sales_inbox="sales@truckbuild.example", resend_api_key=None)


def test_the_sales_email_carries_the_whole_lead(detail: QuoteDetail, settings: Settings) -> None:
    email = mailer.render_sales_email(detail, settings.sales_inbox)

    assert email.to == "sales@truckbuild.example"
    assert "TB-K7MQ4C" in email.subject
    assert "Bristlecone" in email.subject
    assert "$220,100" in email.subject

    for expected in ("Heavy front bumper", "12,000 lb winch", "Dana Reyes", "dana@example.com"):
        assert expected in email.text
    assert "$214,500" in email.text
    assert "$220,100" in email.text


def test_replying_to_the_sales_email_reaches_the_customer(detail: QuoteDetail) -> None:
    assert mailer.render_sales_email(detail, "sales@x.example").reply_to == "dana@example.com"


def test_the_customer_email_leads_with_the_reference(detail: QuoteDetail) -> None:
    email = mailer.render_customer_email(detail)
    assert email.to == "dana@example.com"
    assert "TB-K7MQ4C" in email.subject
    assert "TB-K7MQ4C" in email.text
    assert "Dana" in email.text
    # The customer is told the price is confirmed by us, not by the browser.
    assert "confirmed by us" in email.text


def test_an_enquiry_email_does_not_invent_a_build(detail: QuoteDetail) -> None:
    enquiry = detail.model_copy(
        update={
            "kind": QuoteKind.enquiry,
            "total_cents": None,
            "base_price_cents": None,
            "lines": [],
        }
    )
    email = mailer.render_sales_email(enquiry, "sales@x.example")
    assert "New enquiry" in email.subject
    assert "Build total" not in email.text


async def test_a_missing_api_key_logs_instead_of_sending(
    detail: QuoteDetail, settings: Settings, caplog
) -> None:
    with caplog.at_level("INFO"):
        await mailer.send_lead_emails(detail, settings)
    assert "mail not sent" in caplog.text
    assert "TB-K7MQ4C" in caplog.text


async def test_a_failing_provider_is_logged_and_swallowed(
    detail: QuoteDetail, monkeypatch, caplog
) -> None:
    """By the time this runs the lead is already committed. Raising here would turn a mail
    outage into a lost lead."""

    class BrokenClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> "BrokenClient":
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, *args, **kwargs):
            raise RuntimeError("mail provider is down")

    monkeypatch.setattr(mailer.httpx, "AsyncClient", BrokenClient)

    with caplog.at_level("ERROR"):
        await mailer.send_lead_emails(detail, Settings(resend_api_key="re_broken_key"))

    assert "failed to send" in caplog.text
    assert "dana@example.com" in caplog.text
