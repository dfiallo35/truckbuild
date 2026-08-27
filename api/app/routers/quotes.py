"""Lead submission: a configured build (``POST /v1/quotes``) or a general enquiry
(``POST /v1/enquiries``).

Two rules shape everything here:

- **The server price is the only price.** The request body has no field for a total, and the
  selection is re-validated against the live catalog before anything is stored. What the
  browser computed for the price bar is a UX affordance; what is stored is computed here.
- **A saved lead beats a perfect response.** Once the row is committed the request has
  succeeded. Mail goes out in a background task that swallows its own failures, because a lead
  lost to a mail outage is the expensive failure, not a missing confirmation email.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import Settings, get_settings
from app.db import get_session
from app.errors import FieldError, error_response
from app.models import Option, OptionRule, Platform, Quote, QuoteKind, QuoteLine
from app.schemas.quote import (
    ContactIn,
    EnquiryCreate,
    QuoteCreate,
    QuoteDetail,
    QuoteLineOut,
    QuoteOut,
)
from app.services import mailer
from app.services.pricing import PriceableOption, PriceablePlatform, price_build
from app.services.ratelimit import RateLimiter
from app.services.refs import new_ref
from app.services.rules import OptionRule as PureRule
from app.services.rules import RuleablePlatform, validate_selection
from app.services.spam import screen

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["quotes"])

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_settings = get_settings()
limiter = RateLimiter(
    limit=_settings.quote_rate_limit,
    window_seconds=_settings.quote_rate_limit_window_seconds,
)

REF_ATTEMPTS = 5

# Deliberately vague: naming the control that fired tells an automated submitter what to change.
REJECTED_MESSAGE = "We couldn't accept this submission. Please email us directly."


def _client_ip(request: Request) -> str:
    """The visitor's address, not the web app's.

    The browser never reaches this API directly (see CLAUDE.md) -- every submission arrives from
    the Next.js server action, so without the forwarded header every visitor in the world would
    share one rate-limit bucket. Trusting the header is safe precisely because that proxy is the
    only way in; if this API is ever exposed publicly, the socket peer becomes the honest key.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _guard(request: Request, submission, settings: Settings) -> JSONResponse | None:
    """Spam screening and rate limiting, in that order. Returns a response to send, or ``None``
    to carry on."""
    verdict = screen(submission.website, submission.elapsed_ms, settings.quote_min_submit_ms)
    if verdict.automated:
        logger.warning("rejected submission from %s (%s)", _client_ip(request), verdict.reason)
        return error_response(422, "rejected", REJECTED_MESSAGE)

    limit = limiter.check(_client_ip(request))
    if not limit.allowed:
        return error_response(
            429,
            "rate_limited",
            "That's a lot of submissions in a short time. Try again shortly, or email us.",
            headers={"Retry-After": str(limit.retry_after_seconds)},
        )
    return None


def _platform_by_slug(session: Session, slug: str) -> Platform | None:
    return session.exec(select(Platform).where(Platform.slug == slug)).first()


def _options_of(platform: Platform) -> list[Option]:
    return [option for group in platform.option_groups for option in group.options]


def _rules_of(session: Session, options: list[Option]) -> list[PureRule]:
    slug_by_id = {option.id: option.slug for option in options}
    rows = session.exec(
        select(OptionRule).where(OptionRule.subject_option_id.in_(slug_by_id))
    ).all()
    return [
        PureRule(
            subject=slug_by_id[row.subject_option_id],
            relation=row.relation,
            object=slug_by_id[row.object_option_id],
        )
        for row in rows
        if row.object_option_id in slug_by_id
    ]


def _structural_errors(platform: Platform, selected: list[str]) -> list[FieldError]:
    """Everything wrong with a selection before compatibility rules are even consulted.

    The configurator cannot produce any of these -- ``web/src/lib/build.ts`` repairs the URL it
    reads -- but a hand-rolled POST can, and a build with two cabs and no habitat is not a build.
    """
    known = {option.slug: option for option in _options_of(platform)}
    errors: list[FieldError] = []

    unknown = [slug for slug in selected if slug not in known]
    if unknown:
        errors.append(
            FieldError(
                field="option_slugs",
                code="unknown_option",
                message=f"{platform.name} has no option {', '.join(sorted(set(unknown)))}.",
            )
        )

    duplicates = sorted({slug for slug in selected if selected.count(slug) > 1})
    if duplicates:
        errors.append(
            FieldError(
                field="option_slugs",
                code="duplicate_option",
                message=f"Listed more than once: {', '.join(duplicates)}.",
            )
        )

    chosen = set(selected)
    for group in platform.option_groups:
        in_group = [option for option in group.options if option.slug in chosen]
        if group.selection_mode == "single" and len(in_group) > 1:
            errors.append(
                FieldError(
                    field="option_slugs",
                    code="too_many_in_group",
                    message=f"{group.name} takes one choice, not {len(in_group)}.",
                )
            )
        if group.required and not in_group:
            errors.append(
                FieldError(
                    field="option_slugs",
                    code="missing_required_group",
                    message=f"{group.name} needs a choice.",
                )
            )

    return errors


def _rule_errors(session: Session, platform: Platform, selected: list[str]) -> list[FieldError]:
    options = _options_of(platform)
    name_of = {option.slug: option.name for option in options}
    ruleable = RuleablePlatform(slug=platform.slug, rules=_rules_of(session, options))

    errors: list[FieldError] = []
    for violation in validate_selection(ruleable, selected):
        subject = name_of.get(violation.option, violation.option)
        if violation.kind == "requires":
            needs = name_of.get(violation.needs, violation.needs)
            message = f"{subject} needs the {needs}."
        else:
            conflict = name_of.get(violation.conflicts_with, violation.conflicts_with)
            message = f"{subject} cannot be fitted with the {conflict}."
        errors.append(FieldError(field="option_slugs", code=violation.kind, message=message))
    return errors


def _save(session: Session, quote: Quote) -> Quote:
    """Insert the quote, retrying the reference on the unlikely collision.

    The unique index on ``quote.ref`` is what decides; generating a ref and hoping would put two
    customers on one reference number eventually.
    """
    for _ in range(REF_ATTEMPTS):
        quote.ref = new_ref()
        session.add(quote)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            continue
        session.refresh(quote)
        return quote

    raise RuntimeError(f"could not allocate a unique quote ref in {REF_ATTEMPTS} attempts")


def _detail_of(quote: Quote, contact: ContactIn) -> QuoteDetail:
    return QuoteDetail(
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
        contact=contact,
        intended_use=quote.intended_use,
        timeline=quote.timeline,
        notes=quote.notes,
    )


def _out_of(detail: QuoteDetail) -> QuoteOut:
    return QuoteOut(**detail.model_dump(exclude={"contact", "intended_use", "timeline", "notes"}))


@router.post("/quotes", status_code=201, response_model=None)
def create_quote(
    payload: QuoteCreate,
    request: Request,
    background: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
) -> QuoteOut | JSONResponse:
    rejection = _guard(request, payload, settings)
    if rejection is not None:
        return rejection

    platform = _platform_by_slug(session, payload.platform_slug)
    if platform is None:
        return error_response(
            404,
            "unknown_platform",
            "That platform no longer exists.",
            [FieldError(field="platform_slug", message=f"No platform {payload.platform_slug!r}.")],
        )

    errors = _structural_errors(platform, payload.option_slugs)
    if not errors:
        # Compatibility rules are only meaningful once every slug is real; reporting both at
        # once would explain a conflict between an option and one that does not exist.
        errors = _rule_errors(session, platform, payload.option_slugs)
    if errors:
        return error_response(422, "invalid_selection", "This build needs a change.", errors)

    options = {option.slug: option for option in _options_of(platform)}
    breakdown = price_build(
        PriceablePlatform(
            slug=platform.slug,
            base_price_cents=platform.base_price_cents,
            options=[
                PriceableOption(slug=option.slug, price_delta_cents=option.price_delta_cents)
                for option in options.values()
            ],
        ),
        payload.option_slugs,
    )

    group_of = {
        option.slug: group.name for group in platform.option_groups for option in group.options
    }
    quote = Quote(
        ref="",
        kind=QuoteKind.build,
        platform_id=platform.id,
        platform_slug=platform.slug,
        platform_name=platform.name,
        base_price_cents=breakdown.base_price_cents,
        total_cents=breakdown.total_cents,
        contact_name=payload.contact.name,
        contact_email=payload.contact.email,
        contact_phone=payload.contact.phone,
        intended_use=payload.intended_use,
        timeline=payload.timeline,
        notes=payload.notes,
        source_ip=_client_ip(request),
        lines=[
            QuoteLine(
                option_id=options[slug].id,
                group_name=group_of[slug],
                option_slug=slug,
                option_name=options[slug].name,
                price_delta_cents=options[slug].price_delta_cents,
                sort_order=index,
            )
            for index, slug in enumerate(payload.option_slugs)
        ],
    )

    detail = _detail_of(_save(session, quote), payload.contact)
    logger.info(
        "stored quote %s for %s at %s", detail.ref, detail.platform_slug, detail.total_cents
    )
    background.add_task(mailer.send_lead_emails, detail, settings)
    return _out_of(detail)


@router.post("/enquiries", status_code=201, response_model=None)
def create_enquiry(
    payload: EnquiryCreate,
    request: Request,
    background: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
) -> QuoteOut | JSONResponse:
    """The /contact form. Same storage, same mail, same spam controls -- there is just no build
    to price, so sales reads one list rather than two."""
    rejection = _guard(request, payload, settings)
    if rejection is not None:
        return rejection

    platform = None
    if payload.platform_slug:
        platform = _platform_by_slug(session, payload.platform_slug)
        if platform is None:
            return error_response(
                404,
                "unknown_platform",
                "That platform no longer exists.",
                [
                    FieldError(
                        field="platform_slug", message=f"No platform {payload.platform_slug!r}."
                    )
                ],
            )

    quote = Quote(
        ref="",
        kind=QuoteKind.enquiry,
        platform_id=platform.id if platform else None,
        platform_slug=platform.slug if platform else None,
        platform_name=platform.name if platform else None,
        contact_name=payload.contact.name,
        contact_email=payload.contact.email,
        contact_phone=payload.contact.phone,
        intended_use=payload.intended_use,
        timeline=payload.timeline,
        notes=payload.notes,
        source_ip=_client_ip(request),
    )

    detail = _detail_of(_save(session, quote), payload.contact)
    logger.info("stored enquiry %s", detail.ref)
    background.add_task(mailer.send_lead_emails, detail, settings)
    return _out_of(detail)
