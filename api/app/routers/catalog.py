"""Read-only catalog endpoints. The catalog is small enough that one nested round trip per
platform (or for the whole catalog) costs less than splitting it across many endpoints.
"""

import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models import Asset, AssetKind, OptionRule, Platform
from app.schemas.catalog import (
    AssetOut,
    CatalogOut,
    OptionGroupOut,
    OptionOut,
    OptionRuleOut,
    PlatformOut,
)

router = APIRouter(prefix="/v1", tags=["catalog"])

SessionDep = Annotated[Session, Depends(get_session)]

# Catalog content changes infrequently and is revalidated by the web app's cache tags (see
# docs/decisions.md), so a short browser/CDN cache window plus stale-while-revalidate is enough.
CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=300"


def _serialize_platform(session: Session, platform: Platform) -> PlatformOut:
    assets = session.exec(
        select(Asset).where(Asset.platform_id == platform.id).order_by(Asset.sort_order)
    ).all()
    hero = next((a for a in assets if a.kind == AssetKind.hero), None)
    gallery = [a for a in assets if a.kind == AssetKind.gallery]

    options = [option for group in platform.option_groups for option in group.options]
    option_slug_by_id = {option.id: option.slug for option in options}
    rules = session.exec(
        select(OptionRule).where(OptionRule.subject_option_id.in_(option_slug_by_id))
    ).all()

    return PlatformOut(
        slug=platform.slug,
        name=platform.name,
        purpose=platform.purpose,
        chassis_basis=platform.chassis_basis,
        base_price_cents=platform.base_price_cents,
        spec_highlights=platform.spec_highlights,
        standard_equipment=platform.standard_equipment,
        hero_image=AssetOut(kind=hero.kind, url=hero.url, alt_text=hero.alt_text) if hero else None,
        gallery=[AssetOut(kind=a.kind, url=a.url, alt_text=a.alt_text) for a in gallery],
        option_groups=[
            OptionGroupOut(
                slug=group.slug,
                name=group.name,
                selection_mode=group.selection_mode,
                required=group.required,
                display_style=group.display_style,
                options=[
                    OptionOut(
                        slug=option.slug,
                        name=option.name,
                        price_delta_cents=option.price_delta_cents,
                        description=option.description,
                    )
                    for option in group.options
                ],
            )
            for group in platform.option_groups
        ],
        rules=[
            OptionRuleOut(
                subject=option_slug_by_id[rule.subject_option_id],
                relation=rule.relation,
                object=option_slug_by_id[rule.object_option_id],
            )
            for rule in rules
        ],
    )


def _etag_for(payload: BaseModel) -> str:
    digest = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    return f'W/"{digest[:32]}"'


def _cached_response(request: Request, payload: BaseModel) -> Response:
    etag = _etag_for(payload)
    headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=json.loads(payload.model_dump_json()), headers=headers)


@router.get("/catalog", response_model=None)
def get_catalog(request: Request, session: SessionDep) -> Response:
    platforms = session.exec(select(Platform).order_by(Platform.id)).all()
    catalog = CatalogOut(platforms=[_serialize_platform(session, p) for p in platforms])
    return _cached_response(request, catalog)


@router.get("/platforms/{slug}", response_model=None)
def get_platform(slug: str, request: Request, session: SessionDep) -> Response:
    platform = session.exec(select(Platform).where(Platform.slug == slug)).first()
    if platform is None:
        raise HTTPException(status_code=404, detail=f"no platform with slug {slug!r}")
    return _cached_response(request, _serialize_platform(session, platform))
