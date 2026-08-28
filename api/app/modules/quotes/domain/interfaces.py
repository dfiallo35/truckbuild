"""The ports lead storage depends on, and nothing about how they are filled.

``IQuoteRepository`` is owned here rather than in ``core`` because ``quotes`` owns the data: a
port belongs to the module whose vocabulary it speaks. ``admin`` consumes it -- that is what
``admin -> quotes`` means -- and may not name the Postgres adapter that implements it (the facade
rule, CLAUDE.md); the binding is made at the composition root in ``app/main.py``.

``IMailer`` is *not* here, and deliberately: what gets mailed is the lead summary a use case
produced, which is an ``application`` DTO, and a domain port may not name one. It lives in
``application/interfaces.py`` beside the shape it speaks in.
"""

from abc import abstractmethod

from app.core.domain.interfaces import IBaseRepository
from app.modules.quotes.domain.filters import QuoteFilter
from app.modules.quotes.domain.models import Quote


class IQuoteRepository(IBaseRepository):
    """Storing and reading leads, in domain terms.

    ``create`` carries one promise beyond the base's: the returned ``Quote`` has a ``ref``, and it
    is one no other row holds. Allocating it is storage's business because the unique index is
    what decides -- see ``QuoteRepositoryPostgres.create``.

    Every ``Quote`` that comes back has its lines already loaded. That is a promise of the port,
    not an accident of the adapter: a caller that could trigger a query by reading an attribute is
    a caller that can reintroduce an N+1.

    One trap worth naming, because it costs ten minutes every time: ``list`` is a method here, so
    it shadows the builtin inside the body of any class implementing this. An annotation like
    ``list[str]`` written *after* it raises ``TypeError: 'function' object is not subscriptable``
    at class-creation time. ``from __future__ import annotations`` at the top of the
    implementation is the fix that does not rename the port.
    """

    @abstractmethod
    def create(self, entity: Quote) -> Quote:
        pass  # pragma: no cover

    @abstractmethod
    def list(self, filters: QuoteFilter) -> list[Quote]:
        pass  # pragma: no cover

    @abstractmethod
    def by_ref(self, ref: str) -> Quote | None:
        """One lead by its public reference, or ``None``. The number a customer reads back over
        the phone, which is why it is a lookup of its own rather than a filter every caller
        rebuilds."""
        pass  # pragma: no cover
