"""Domain <-> DTO: what a submission becomes, and what a stored lead is allowed to look like.

The other half of the pair whose first half is ``infrastructure/postgres/mappers.py``. That one
knows about columns and foreign keys; this one knows about the wire.

``to_domain`` is where the ``Quote``/``QuoteLine`` aggregate is built -- once. Until Stage 11 it
was written twice, inline in two router handlers, which is how the enquiry path came to differ
from the build path in ways nobody had decided on. Pricing happens here too, through ``catalog``'s
own ``price_build``: the lines and the totals are the same fact recorded twice, and building them
apart is how they drift.
"""

from app.core.application.mappers import BaseMapper
from app.modules.catalog.domain.models import Platform
from app.modules.catalog.domain.pricing import price_build
from app.modules.quotes.application.dtos import (
    ContactInput,
    LeadCreateRequest,
    QuoteDetailOutput,
    QuoteLineOutput,
)
from app.modules.quotes.domain.enums import QuoteKind
from app.modules.quotes.domain.models import Quote, QuoteLine


class QuoteMapper(BaseMapper):
    def to_api(self, entity: Quote) -> QuoteDetailOutput:
        """Read a stored lead back out. The one builder for all three readers -- the submission
        response, the emails, and the admin detail endpoint -- so a lead reads the same however
        it is reached, and a new field cannot reach one of them and not the others."""
        return QuoteDetailOutput(
            ref=entity.ref,
            kind=entity.kind,
            platform_slug=entity.platform_slug,
            platform_name=entity.platform_name,
            base_price_cents=entity.base_price_cents,
            total_cents=entity.total_cents,
            lines=[
                QuoteLineOutput(
                    group_name=line.group_name,
                    option_slug=line.option_slug,
                    option_name=line.option_name,
                    price_delta_cents=line.price_delta_cents,
                )
                for line in entity.lines
            ],
            created_at=entity.created_at,
            contact=ContactInput(
                name=entity.contact_name,
                email=entity.contact_email,
                phone=entity.contact_phone,
            ),
            intended_use=entity.intended_use,
            timeline=entity.timeline,
            notes=entity.notes,
        )

    def to_domain(
        self,
        create_request: LeadCreateRequest,
        platform: Platform | None = None,
        source_ip: str = "",
    ) -> Quote:
        """The whole aggregate, priced.

        Called only after the selection has been judged: ``price_build`` raises on a slug the
        platform does not have, which is a 500 rather than the 422 that fault deserves. That
        ordering is ``SubmitQuoteUseCase``'s to keep -- see its ``exec``.

        ``ref`` is left empty. The unique index is what decides a reference is free, so the
        repository allocates one on insert.
        """
        quote = Quote(
            kind=create_request.kind,
            platform_id=platform.id if platform else None,
            platform_slug=platform.slug if platform else None,
            platform_name=platform.name if platform else None,
            contact_name=create_request.contact.name,
            contact_email=create_request.contact.email,
            contact_phone=create_request.contact.phone,
            intended_use=create_request.intended_use,
            timeline=create_request.timeline,
            notes=create_request.notes,
            source_ip=source_ip,
        )
        if create_request.kind != QuoteKind.build or platform is None:
            # An enquiry has no build: no base price, no total, no lines -- even when it names a
            # platform it is interested in.
            return quote

        selected: list[str] = create_request.option_slugs
        options = {option.slug: option for option in platform.options}
        group_of = {
            option.slug: group.name for group in platform.option_groups for option in group.options
        }
        breakdown = price_build(platform, selected)

        quote.base_price_cents = breakdown.base_price_cents
        quote.total_cents = breakdown.total_cents
        quote.lines = [
            QuoteLine(
                option_id=options[slug].id,
                group_name=group_of[slug],
                option_slug=slug,
                option_name=options[slug].name,
                price_delta_cents=options[slug].price_delta_cents,
                sort_order=index,
            )
            for index, slug in enumerate(selected)
        ]
        return quote

    def to_update(self, entity: Quote, update_request) -> Quote:  # pragma: no cover
        """Not implemented, and deliberately not faked. A submitted lead is a record of what was
        offered on a date; nothing in this service edits one."""
        raise NotImplementedError("a stored lead is a record of what was offered, not a draft")
