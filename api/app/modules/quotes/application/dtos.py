"""The shapes crossing this module's boundary: what a submission asks for, and what it answers
with.

These *are* the wire contract for ``POST /v1/quotes`` and ``POST /v1/enquiries``. They live here
rather than in ``presentation`` for the reason ``core/application/dtos.py`` gives for the error
body: pure pydantic, so a use case can build one and a test can hold one without a web framework,
while FastAPI is still free to parse and serialize them at the edge.

Note what ``QuoteCreateRequest`` does *not* accept: a price, and a source address. A total sent by
a browser is user input, not a fact, so the field simply does not exist and an extra one is
dropped by ``extra="ignore"``; the server recomputes it from the option slugs. The address is not
in the body either -- it is read from the forwarded header by the router and handed to the use
case as an argument, so no client can name its own.
"""

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.application.dtos import BaseCreateRequest, BaseOutput
from app.modules.quotes.domain.enums import QuoteKind


class ContactInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(default="", max_length=40)


class LeadCreateRequest(BaseCreateRequest):
    """Fields every lead form sends, whatever it is asking for.

    ``kind`` is a ``ClassVar`` rather than a field: which of the two endpoints was posted to is
    decided by the route, not by the body, and a body field would let a caller file an enquiry as
    a build. The mapper reads it off the class.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    kind: ClassVar[QuoteKind]

    contact: ContactInput
    intended_use: str = Field(default="", max_length=4000)
    timeline: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=4000)

    # Spam controls, both filled in by the form rather than by the person. ``website`` is the
    # honeypot: rendered, hidden, and expected to stay empty. ``elapsed_ms`` is how long the
    # form was open. See app/modules/quotes/domain/spam.py.
    website: str = Field(default="", max_length=200)
    elapsed_ms: int | None = None


class QuoteCreateRequest(LeadCreateRequest):
    kind: ClassVar[QuoteKind] = QuoteKind.build

    platform_slug: str = Field(min_length=1, max_length=120)
    option_slugs: list[str] = Field(default_factory=list, max_length=200)


class EnquiryCreateRequest(LeadCreateRequest):
    """The general enquiry behind /contact. A platform may be named as an interest, but there
    is no build to price."""

    kind: ClassVar[QuoteKind] = QuoteKind.enquiry

    platform_slug: str | None = Field(default=None, max_length=120)


class QuoteLineOutput(BaseOutput):
    group_name: str
    option_slug: str
    option_name: str
    price_delta_cents: int


class QuoteOutput(BaseOutput):
    """What the customer is shown after submitting. ``total_cents`` is the server's own
    computation and is null for an enquiry, which has no build attached."""

    ref: str
    kind: QuoteKind
    platform_slug: str | None
    platform_name: str | None
    base_price_cents: int | None
    total_cents: int | None
    lines: list[QuoteLineOutput]
    created_at: datetime

    @classmethod
    def of(cls, detail: "QuoteDetailOutput") -> "QuoteOutput":
        """Narrow a full lead to the part the browser that submitted it may see.

        A projection rather than a second mapping, so a field added to the detail is either
        carried here or deliberately excluded -- it cannot be quietly forgotten by one of two
        builders that have drifted apart.
        """
        return cls(**detail.model_dump(exclude={"contact", "intended_use", "timeline", "notes"}))


class QuoteDetailOutput(QuoteOutput):
    """The whole lead, including the details only staff should see. What the emails are rendered
    from and what the admin detail endpoint answers with -- never returned to the browser that
    submitted it."""

    contact: ContactInput
    intended_use: str
    timeline: str
    notes: str
