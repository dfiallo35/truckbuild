"""Outbound lead mail via Resend: the implementation of ``IMailer``.

The contract that matters: **sending is best-effort and never fails the request.** By the time
this runs the lead is already committed to Postgres, and losing it to a transient mail problem
would be the worse outcome by far -- so every failure is logged loudly and swallowed. A missing
``RESEND_API_KEY`` is not an error either; in development the rendered message goes to the log,
which is also what makes the copy reviewable without sending anything.

What it renders *from* is a ``QuoteDetailOutput`` -- the lead summary the use case produced.
Until Stage 11 it was a response schema out of ``presentation/``, which made an outbound adapter
depend on the shape of an HTTP body for no reason anyone could state.
"""

import logging
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.modules.quotes.application.dtos import QuoteDetailOutput
from app.modules.quotes.application.interfaces import IMailer
from app.modules.quotes.domain.enums import QuoteKind

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


def _build_summary(lead: QuoteDetailOutput) -> str:
    """The build as a work order: one line per item, amounts in a column.

    Labels are padded to the longest one rather than clipped to a fixed width -- an option
    truncated mid-word ("Long-Travel Suspension, All-Terra") is worse to read than a long line
    the mail client wraps.
    """
    rows = [("Base vehicle", money(lead.base_price_cents))]
    rows += [
        (f"{line.group_name} — {line.option_name}", money(line.price_delta_cents))
        for line in lead.lines
    ]

    label_width = max(len(label) for label, _ in rows)
    amount_width = max(len(amount) for _, amount in rows)

    lines = [f"{lead.platform_name} ({lead.platform_slug})"]
    lines += [f"  {label:<{label_width}}  {amount:>{amount_width}}" for label, amount in rows]
    lines.append("  " + "-" * (label_width + amount_width + 2))
    lines.append(f"  {'Build total':<{label_width}}  {money(lead.total_cents):>{amount_width}}")
    return "\n".join(lines)


def _context(lead: QuoteDetailOutput) -> str:
    fields = [
        ("Name", lead.contact.name),
        ("Email", lead.contact.email),
        ("Phone", lead.contact.phone),
        ("Timeline", lead.timeline),
        ("Intended use", lead.intended_use),
        ("Notes", lead.notes),
    ]
    return "\n".join(f"{label}: {value}" for label, value in fields if value)


def render_sales_email(lead: QuoteDetailOutput, sales_inbox: str) -> Email:
    is_build = lead.kind == QuoteKind.build
    subject = (
        f"New build request {lead.ref} — {lead.platform_name} {money(lead.total_cents)}"
        if is_build
        else f"New enquiry {lead.ref} — {lead.contact.name}"
    )
    body = [f"Reference {lead.ref}", ""]
    if is_build:
        body += [_build_summary(lead), ""]
    elif lead.platform_name:
        body += [f"Interested in: {lead.platform_name}", ""]
    body += [_context(lead), "", f"Submitted {lead.created_at:%Y-%m-%d %H:%M UTC}"]

    return Email(
        to=sales_inbox,
        subject=subject,
        text="\n".join(body),
        # So hitting Reply in the inbox answers the customer, not the robot.
        reply_to=lead.contact.email,
    )


def render_customer_email(lead: QuoteDetailOutput) -> Email:
    is_build = lead.kind == QuoteKind.build
    body = [
        f"{lead.contact.name.split(' ')[0]},",
        "",
        (
            "Thanks — your build is with us. A build specialist will come back to you within one "
            "business day."
            if is_build
            else "Thanks for getting in touch. We'll come back to you within one business day."
        ),
        "",
        f"Your reference is {lead.ref}. Quote it in any reply and we'll pick up where you "
        "left off.",
        "",
    ]
    if is_build:
        body += [
            _build_summary(lead),
            "",
            "That total covers the platform and the options you selected. Final pricing is "
            "confirmed by us on order — freight, registration, and any custom work are quoted "
            "with it.",
            "",
        ]
    body += ["— TruckBuild"]

    return Email(
        to=lead.contact.email,
        subject=f"Your TruckBuild request {lead.ref}",
        text="\n".join(body),
    )


class ResendMailer(IMailer):
    """The one implementation. Holds the settings rather than taking them per call, so the
    router that schedules it needs to know nothing but the lead."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_lead_emails(self, lead: QuoteDetailOutput) -> None:
        """Notify sales, then confirm to the customer. Never raises."""
        for email in (
            render_sales_email(lead, self.settings.sales_inbox),
            render_customer_email(lead),
        ):
            await self._send(email)

    async def _send(self, email: Email) -> None:
        if not self.settings.resend_api_key:
            logger.info(
                "mail not sent (no RESEND_API_KEY); would have sent to %s: %s\n%s",
                email.to,
                email.subject,
                email.text,
            )
            return

        payload: dict[str, object] = {
            "from": self.settings.mail_from,
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
                    headers={"Authorization": f"Bearer {self.settings.resend_api_key}"},
                )
                response.raise_for_status()
        except Exception:
            # The lead is already saved. Log it with the address so it can be resent by hand, and
            # let the request succeed.
            logger.exception("failed to send %r to %s", email.subject, email.to)
