"""Request and response shapes for POST /v1/quotes and POST /v1/enquiries.

Note what ``QuoteCreate`` does *not* accept: a price. A total sent by a browser is user input,
not a fact, so the field simply does not exist here and an extra one is dropped by
``extra="ignore"``. The server recomputes the total from the option slugs -- see
``app/routers/quotes.py`` and docs/decisions.md.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import QuoteKind


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
    """The whole lead, including the details only staff should see. Used to render the emails,
    and by the admin endpoints in stage 6 -- never returned to the browser that submitted it."""

    contact: ContactIn
    intended_use: str
    timeline: str
    notes: str
