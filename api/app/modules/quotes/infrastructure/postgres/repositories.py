"""Every query the quotes module makes, in one place.

Two things live here that used to be spread across two routers, and both are storage facts rather
than business ones:

- **The write, including its retry.** ``create`` allocates a reference, inserts, and starts again
  on the one-in-a-few-hundred-million collision. The unique index on ``quote.ref`` is what
  decides a ref is free -- generating one and hoping would put two customers on one reference
  number eventually -- and coping with the index is the adapter's job, not the use case's.
- **The read, including how a lead list is narrowed.** ``filter`` applies the shared narrowing
  first and then this module's own, which is the pattern every feature repository follows so that
  ``id_eq``, the window and the ordering keep behaving identically wherever they are used.

``list`` issues two statements whatever it is asked for -- the quotes, then every line belonging
to them -- and hands the mapper what it needs. Nothing above this line holds a session, so nothing
above this line can add a third by reading an attribute.
"""

# `list` is a method on this class (it is the port's name for "read many"), which shadows the
# builtin inside the class body -- so `list[str]` in any annotation below it would resolve to the
# method. Deferring annotation evaluation is the fix that does not rename the port.
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import Select
from sqlmodel import col, select

from app.core.infrastructure.postgres.repositories import BaseRepositoryPostgres
from app.modules.quotes.domain.filters import QuoteFilter
from app.modules.quotes.domain.interfaces import IQuoteRepository
from app.modules.quotes.domain.models import Quote
from app.modules.quotes.domain.refs import new_ref
from app.modules.quotes.infrastructure.postgres.mappers import QuoteMapper
from app.modules.quotes.infrastructure.postgres.tables import QuoteLineTable, QuoteTable

REF_ATTEMPTS = 5


class QuoteRepositoryPostgres(BaseRepositoryPostgres, IQuoteRepository):
    mapper = QuoteMapper()
    table_class = QuoteTable

    def filter(self, filters: QuoteFilter, query: Select) -> Select:
        query = super().filter(filters, query)

        if filters.ref_eq is not None:
            query = query.where(col(QuoteTable.ref) == filters.ref_eq)
        if filters.kind_eq is not None:
            query = query.where(col(QuoteTable.kind) == filters.kind_eq)
        if filters.platform_slug_eq is not None:
            query = query.where(col(QuoteTable.platform_slug) == filters.platform_slug_eq)
        if filters.search:
            term = f"%{_escape_like(filters.search.strip())}%"
            query = query.where(
                or_(
                    col(QuoteTable.ref).ilike(term, escape="\\"),
                    col(QuoteTable.contact_name).ilike(term, escape="\\"),
                    col(QuoteTable.contact_email).ilike(term, escape="\\"),
                )
            )

        if filters.order_by:
            # The tie-break, in whichever direction the caller asked for: two leads can share a
            # `created_at` to the microsecond under a test's clock, and a page boundary that
            # wobbles drops or repeats a lead. Skipped when there is no ordering at all, which is
            # what `count` asks for.
            key = col(QuoteTable.id)
            query = query.order_by(key.desc() if filters.order_by.startswith("-") else key)

        return query

    def create(self, entity: Quote) -> Quote:
        """Insert the lead and its lines, retrying the reference on the unlikely collision.

        This is the one write in the service that commits rather than flushing: the request has
        succeeded once the row is durable, and the mail that follows goes out in a background
        task that cannot roll it back.
        """
        table = self.mapper.to_table(entity)

        for _ in range(REF_ATTEMPTS):
            table.ref = new_ref()
            self.session.add(table)
            try:
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                continue
            self.session.refresh(table)
            return self.mapper.to_domain(table, list(table.lines))

        raise RuntimeError(f"could not allocate a unique quote ref in {REF_ATTEMPTS} attempts")

    def list(self, filters: QuoteFilter) -> list[Quote]:
        rows = self.session.exec(self.filter(filters, select(QuoteTable))).all()
        lines = self._lines_for(rows)
        return [self.mapper.to_domain(row, lines[row.id]) for row in rows]

    def by_ref(self, ref: str) -> Quote | None:
        quotes = self.list(QuoteFilter(ref_eq=ref, limit=1))
        return quotes[0] if quotes else None

    def _lines_for(self, quotes: list[QuoteTable]) -> dict[int, list[QuoteLineTable]]:
        """One statement, whatever the length of ``quotes`` -- the alternative is a query per
        lead, issued invisibly by reading ``quote.lines`` in a loop."""
        rows = self.session.exec(
            select(QuoteLineTable)
            .where(col(QuoteLineTable.quote_id).in_([quote.id for quote in quotes]))
            .order_by(col(QuoteLineTable.sort_order), col(QuoteLineTable.id))
        ).all()

        by_quote: dict[int, list[QuoteLineTable]] = defaultdict(list)
        for row in rows:
            by_quote[row.quote_id].append(row)
        return by_quote


def _escape_like(term: str) -> str:
    """``%`` and ``_`` are wildcards to ``ILIKE``; a search for ``100%`` should look for that."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
