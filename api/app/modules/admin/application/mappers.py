"""``quotes.domain.Quote`` -> ``admin``'s own staff-facing shapes.

The other half of the split this stage makes: a staff-facing lead view and a customer-facing
submission response are two audiences whose fields will diverge the first time either changes, so
``admin`` stops reading leads through ``quotes``' ``QuoteMapper``.
"""

from app.core.application.mappers import BaseMapper
from app.modules.admin.application.dtos import (
    ContactOutput,
    QuoteDetailOutput,
    QuoteLineDetailOutput,
    QuoteSummaryOutput,
)
from app.modules.quotes.domain.models import Quote


class AdminQuoteMapper(BaseMapper):
    def to_api(self, entity: Quote) -> QuoteSummaryOutput:
        return QuoteSummaryOutput(
            ref=entity.ref,
            kind=entity.kind,
            created_at=entity.created_at,
            contact_name=entity.contact_name,
            contact_email=entity.contact_email,
            platform_slug=entity.platform_slug,
            platform_name=entity.platform_name,
            total_cents=entity.total_cents,
            line_count=len(entity.lines),
        )

    def to_detail(self, entity: Quote) -> QuoteDetailOutput:
        return QuoteDetailOutput(
            ref=entity.ref,
            kind=entity.kind,
            platform_slug=entity.platform_slug,
            platform_name=entity.platform_name,
            base_price_cents=entity.base_price_cents,
            total_cents=entity.total_cents,
            lines=[
                QuoteLineDetailOutput(
                    group_name=line.group_name,
                    option_slug=line.option_slug,
                    option_name=line.option_name,
                    price_delta_cents=line.price_delta_cents,
                )
                for line in entity.lines
            ],
            created_at=entity.created_at,
            contact=ContactOutput(
                name=entity.contact_name,
                email=entity.contact_email,
                phone=entity.contact_phone,
            ),
            intended_use=entity.intended_use,
            timeline=entity.timeline,
            notes=entity.notes,
        )

    # admin is read-only over leads: it stores nothing and edits nothing. Declared rather than
    # deleted because BaseMapper requires them -- but not faked, because scaffolding that lies
    # about being exercised is worse than scaffolding that admits it.
    def to_domain(self, create_request) -> Quote:  # pragma: no cover - read-only module
        raise NotImplementedError("admin reads leads, it does not create them")

    def to_update(self, entity: Quote, update_request) -> Quote:  # pragma: no cover
        raise NotImplementedError("a stored lead is a record of what was offered, not a draft")
