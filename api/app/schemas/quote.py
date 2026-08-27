"""Request and response shapes for POST /v1/quotes and POST /v1/enquiries.

Note what ``QuoteCreate`` does *not* accept: a price. A total sent by a browser is user input,
not a fact, so the field simply does not exist here and an extra one is dropped by
``extra="ignore"``. The server recomputes the total from the option slugs -- see
``app/routers/quotes.py`` and docs/decisions.md.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import QuoteKind

if TYPE_CHECKING:  # a wire shape should not need the table at runtime, only to describe one
    from app.models import Quote


class ContactIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(default="", max_length=40)


class _SubmissionIn(BaseModel):
    """Fields every lead form sends, whatever it is asking for."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    contact: ContactIn
    intended_use: str = Field(default="", max_length=4000)
    timeline: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=4000)

    # Spam controls, both filled in by the form rather than by the person. ``website`` is the
    # honeypot: rendered, hidden, and expected to stay empty. ``elapsed_ms`` is how long the
    # form was open. See app/services/spam.py.
    website: str = Field(default="", max_length=200)
    elapsed_ms: int | None = None


class QuoteCreate(_SubmissionIn):
    platform_slug: str = Field(min_length=1, max_length=120)
    option_slugs: list[str] = Field(default_factory=list, max_length=200)


class EnquiryCreate(_SubmissionIn):
    """The general enquiry behind /contact. A platform may be named as an interest, but there
    is no build to price."""

    platform_slug: str | None = Field(default=None, max_length=120)


class QuoteLineOut(BaseModel):
    group_name: str
    option_slug: str
    option_name: str
    price_delta_cents: int


class QuoteOut(BaseModel):
    """What the customer is shown after submitting. ``total_cents`` is the server's own
    computation and is null for an enquiry, which has no build attached."""

    ref: str
    kind: QuoteKind
    platform_slug: str | None
    platform_name: str | None
    base_price_cents: int | None
    total_cents: int | None
    lines: list[QuoteLineOut]
    created_at: datetime


class QuoteDetail(QuoteOut):
    """The whole lead, including the details only staff should see. Used to render the emails
    and by the admin endpoints -- never returned to the browser that submitted it."""

    contact: ContactIn
    intended_use: str
    timeline: str
    notes: str

    @classmethod
    def from_row(cls, quote: "Quote") -> "QuoteDetail":
        """Read a stored lead back out. The one builder for both callers -- the submission
        response and the admin detail endpoint -- so a lead reads the same however it is
        reached, and a new field cannot reach one of them and not the other."""
        return cls(
            ref=quote.ref,
            kind=quote.kind,
            platform_slug=quote.platform_slug,
            platform_name=quote.platform_name,
            base_price_cents=quote.base_price_cents,
            total_cents=quote.total_cents,
            lines=[
                QuoteLineOut(
                    group_name=line.group_name,
                    option_slug=line.option_slug,
                    option_name=line.option_name,
                    price_delta_cents=line.price_delta_cents,
                )
                for line in quote.lines
            ],
            created_at=quote.created_at,
            contact=ContactIn(
                name=quote.contact_name, email=quote.contact_email, phone=quote.contact_phone
            ),
            intended_use=quote.intended_use,
            timeline=quote.timeline,
            notes=quote.notes,
        )
