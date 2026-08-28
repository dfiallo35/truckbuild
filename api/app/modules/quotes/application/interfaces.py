"""The port outbound lead mail is sent through.

Here rather than in ``domain/interfaces.py`` beside ``IQuoteRepository`` because of what it
speaks in: a mailer renders the lead summary a use case produced -- ``QuoteDetailOutput``, an
``application`` DTO -- and a ``domain`` port may not name one.

What it is *not* is the point. Until Stage 11 the mail adapter imported ``QuoteDetail`` from
``presentation/schemas.py``, so an outbound adapter depended on the shape of an HTTP response
body: change the wire and the emails break, for no reason anyone could state. Both now depend on
the same application shape, and neither on the other.
"""

from abc import ABC, abstractmethod

from app.modules.quotes.application.dtos import QuoteDetailOutput


class IMailer(ABC):
    """Telling sales and the customer that a lead arrived.

    **Never raises.** By the time this is called the lead is committed, and losing it to a
    transient mail problem would be the worse outcome by far -- so the contract is that every
    failure is logged and swallowed by the implementation. The scheduling is the router's; see
    ``presentation/quotes_api.py``.
    """

    @abstractmethod
    async def send_lead_emails(self, lead: QuoteDetailOutput) -> None:
        pass  # pragma: no cover
