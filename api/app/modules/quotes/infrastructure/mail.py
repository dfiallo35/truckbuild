"""Outbound lead mail via Resend.

The contract that matters: **sending is best-effort and never fails the request.** By the time
this runs the lead is already committed to Postgres, and losing it to a transient mail problem
would be the worse outcome by far -- so every failure is logged loudly and swallowed. A missing
``RESEND_API_KEY`` is not an error either; in development the rendered message goes to the log,
which is also what makes the copy reviewable without sending anything.
"""

import logging
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.modules.quotes.domain.enums import QuoteKind
from app.modules.quotes.presentation.schemas import QuoteDetail

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    reply_to: str | None = None


def money(cents: int | None) -> str:
    return "—" if cents is None else f"${cents / 100:,.0f}"


def _build_summary(detail: QuoteDetail) -> str:
    """The build as a work order: one line per item, amounts in a column.

    Labels are padded to the longest one rather than clipped to a fixed width -- an option
    truncated mid-word ("Long-Travel Suspension, All-Terra") is worse to read than a long line
    the mail client wraps.
    """
    rows = [("Base vehicle", money(detail.base_price_cents))]
    rows += [
        (f"{line.group_name} — {line.option_name}", money(line.price_delta_cents))
        for line in detail.lines
    ]

    label_width = max(len(label) for label, _ in rows)
    amount_width = max(len(amount) for _, amount in rows)

    lines = [f"{detail.platform_name} ({detail.platform_slug})"]
    lines += [f"  {label:<{label_width}}  {amount:>{amount_width}}" for label, amount in rows]
    lines.append("  " + "-" * (label_width + amount_width + 2))
    lines.append(f"  {'Build total':<{label_width}}  {money(detail.total_cents):>{amount_width}}")
    return "\n".join(lines)


def _context(detail: QuoteDetail) -> str:
    fields = [
        ("Name", detail.contact.name),
        ("Email", detail.contact.email),
        ("Phone", detail.contact.phone),
        ("Timeline", detail.timeline),
        ("Intended use", detail.intended_use),
        ("Notes", detail.notes),
    ]
    return "\n".join(f"{label}: {value}" for label, value in fields if value)


def render_sales_email(detail: QuoteDetail, sales_inbox: str) -> Email:
    is_build = detail.kind == QuoteKind.build
    subject = (
        f"New build request {detail.ref} — {detail.platform_name} {money(detail.total_cents)}"
        if is_build
        else f"New enquiry {detail.ref} — {detail.contact.name}"
    )
    body = [f"Reference {detail.ref}", ""]
    if is_build:
        body += [_build_summary(detail), ""]
    elif detail.platform_name:
        body += [f"Interested in: {detail.platform_name}", ""]
    body += [_context(detail), "", f"Submitted {detail.created_at:%Y-%m-%d %H:%M UTC}"]

    return Email(
        to=sales_inbox,
        subject=subject,
        text="\n".join(body),
        # So hitting Reply in the inbox answers the customer, not the robot.
        reply_to=detail.contact.email,
    )


def render_customer_email(detail: QuoteDetail) -> Email:
    is_build = detail.kind == QuoteKind.build
    body = [
        f"{detail.contact.name.split(' ')[0]},",
        "",
        (
            "Thanks — your build is with us. A build specialist will come back to you within one "
            "business day."
            if is_build
            else "Thanks for getting in touch. We'll come back to you within one business day."
        ),
        "",
        f"Your reference is {detail.ref}. Quote it in any reply and we'll pick up where you "
        "left off.",
        "",
    ]
    if is_build:
        body += [
            _build_summary(detail),
            "",
            "That total covers the platform and the options you selected. Final pricing is "
            "confirmed by us on order — freight, registration, and any custom work are quoted "
            "with it.",
            "",
        ]
    body += ["— TruckBuild"]

    return Email(
        to=detail.contact.email,
        subject=f"Your TruckBuild request {detail.ref}",
        text="\n".join(body),
    )


async def send_lead_emails(detail: QuoteDetail, settings: Settings) -> None:
    """Notify sales, then confirm to the customer. Never raises."""
    for email in (render_sales_email(detail, settings.sales_inbox), render_customer_email(detail)):
        await _send(email, settings)


async def _send(email: Email, settings: Settings) -> None:
    if not settings.resend_api_key:
        logger.info(
            "mail not sent (no RESEND_API_KEY); would have sent to %s: %s\n%s",
            email.to,
            email.subject,
            email.text,
        )
        return

    payload: dict[str, object] = {
        "from": settings.mail_from,
        "to": [email.to],
        "subject": email.subject,
        "text": email.text,
    }
    if email.reply_to:
        payload["reply_to"] = [email.reply_to]

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(
                RESEND_ENDPOINT,
                json=payload,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            )
            response.raise_for_status()
    except Exception:
        # The lead is already saved. Log it with the address so it can be resent by hand, and
        # let the request succeed.
        logger.exception("failed to send %r to %s", email.subject, email.to)
