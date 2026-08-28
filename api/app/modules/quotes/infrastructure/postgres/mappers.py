"""Table <-> domain translation for a lead.

Field copying rather than assembly, unlike the catalog's -- a quote is one row plus its lines,
not a graph. What it has in common with the catalog's is the rule that matters: the lines are
passed *in*, already fetched by the repository, rather than read off ``table.lines`` here. A
mapper with no session cannot lazy-load, whatever it is asked for.
"""

from app.core.infrastructure.postgres.mappers import BaseMapper
from app.modules.quotes.domain.models import Quote, QuoteLine
from app.modules.quotes.infrastructure.postgres.tables import QuoteLineTable, QuoteTable


class QuoteMapper(BaseMapper):
    def to_domain(self, table: QuoteTable, lines: list[QuoteLineTable]) -> Quote:
        """``lines`` is required rather than defaulted: a quote mapped without them would
        serialize as a valid-looking build with nothing on it, and the confirmation email would
        go out that way. A ``TypeError`` at the call site is the better failure."""
        return Quote(
            id=table.id,
            created_at=table.created_at,
            updated_at=table.updated_at,
            ref=table.ref,
            kind=table.kind,
            platform_id=table.platform_id,
            platform_slug=table.platform_slug,
            platform_name=table.platform_name,
            base_price_cents=table.base_price_cents,
            total_cents=table.total_cents,
            contact_name=table.contact_name,
            contact_email=table.contact_email,
            contact_phone=table.contact_phone,
            intended_use=table.intended_use,
            timeline=table.timeline,
            notes=table.notes,
            source_ip=table.source_ip,
            lines=[
                QuoteLine(
                    id=row.id,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    quote_id=row.quote_id,
                    option_id=row.option_id,
                    group_name=row.group_name,
                    option_slug=row.option_slug,
                    option_name=row.option_name,
                    price_delta_cents=row.price_delta_cents,
                    sort_order=row.sort_order,
                )
                for row in lines
            ],
        )

    def to_table(self, entity: Quote) -> QuoteTable:
        """The whole aggregate as one object graph, so the relationship's cascade writes the
        quote and its lines in one insert rather than the caller ordering two."""
        return QuoteTable(
            ref=entity.ref,
            kind=entity.kind,
            platform_id=entity.platform_id,
            platform_slug=entity.platform_slug,
            platform_name=entity.platform_name,
            base_price_cents=entity.base_price_cents,
            total_cents=entity.total_cents,
            contact_name=entity.contact_name,
            contact_email=entity.contact_email,
            contact_phone=entity.contact_phone,
            intended_use=entity.intended_use,
            timeline=entity.timeline,
            notes=entity.notes,
            source_ip=entity.source_ip,
            lines=[
                QuoteLineTable(
                    option_id=line.option_id,
                    group_name=line.group_name,
                    option_slug=line.option_slug,
                    option_name=line.option_name,
                    price_delta_cents=line.price_delta_cents,
                    sort_order=line.sort_order,
                )
                for line in entity.lines
            ],
        )
