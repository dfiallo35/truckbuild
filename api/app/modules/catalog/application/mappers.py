"""Domain -> DTO: what a caller is allowed to see of a platform.

The other half of the pair whose first half is ``infrastructure/postgres/mappers.py``. That one
knows about columns and foreign keys; this one knows about the wire. Keeping them apart is what
lets a column be added without the response moving, and a response field be added without a
migration -- and it is why ``Asset.sort_order`` reaches ``LayerOutput.z_index`` here rather than
being named ``z_index`` all the way down into the schema.
"""

from app.core.application.mappers import BaseMapper
from app.modules.catalog.application.dtos import (
    AssetOutput,
    BuildModelOutput,
    LayerOutput,
    OptionGroupOutput,
    OptionModelEffectOutput,
    OptionOutput,
    OptionRuleOutput,
    PlatformOutput,
)
from app.modules.catalog.domain.models import (
    Asset,
    BuildModel,
    Option,
    OptionGroup,
    OptionModelEffect,
    Platform,
)


def _asset(asset: Asset | None) -> AssetOutput | None:
    if asset is None:
        return None
    return AssetOutput(kind=asset.kind, url=asset.url, alt_text=asset.alt_text)


def _layer(asset: Asset | None) -> LayerOutput | None:
    """``sort_order`` becomes ``z_index``: on the way in it is "where this sits in its owner's
    list", on the way out it is "where this sits in the viewer composite"."""
    if asset is None:
        return None
    return LayerOutput(url=asset.url, alt_text=asset.alt_text, z_index=asset.sort_order)


def _model(model: BuildModel | None) -> BuildModelOutput | None:
    """A model with no ``url`` maps to ``None``: from a consumer's point of view a model whose
    bytes are not uploaded is not a model, and emitting ``{"url": ""}`` would force every reader
    to check for an empty string -- the exact class of bug the Zod boundary exists to prevent."""
    if model is None or not model.url:
        return None
    return BuildModelOutput(
        url=model.url,
        alt_text=model.alt_text,
        camera_orbit_deg=model.camera_orbit_deg,
        camera_distance_m=model.camera_distance_m,
        camera_target_y_m=model.camera_target_y_m,
    )


def _model_effect(effect: OptionModelEffect | None) -> OptionModelEffectOutput | None:
    if effect is None:
        return None
    return OptionModelEffectOutput(
        nodes=effect.nodes,
        material_target=effect.material_target,
        base_color_hex=effect.base_color_hex,
        metalness=effect.metalness,
        roughness=effect.roughness,
    )


class PlatformMapper(BaseMapper):
    def to_api(self, entity: Platform) -> PlatformOutput:
        return PlatformOutput(
            slug=entity.slug,
            name=entity.name,
            purpose=entity.purpose,
            chassis_basis=entity.chassis_basis,
            base_price_cents=entity.base_price_cents,
            spec_highlights=entity.spec_highlights,
            standard_equipment=entity.standard_equipment,
            hero_image=_asset(entity.hero_image),
            viewer_base=_layer(entity.viewer_base),
            gallery=[_asset(asset) for asset in entity.gallery],
            model=_model(entity.model),
            option_groups=[self._group(group) for group in entity.option_groups],
            rules=[
                OptionRuleOutput(subject=rule.subject, relation=rule.relation, object=rule.object)
                for rule in entity.rules
            ],
        )

    def _group(self, group: OptionGroup) -> OptionGroupOutput:
        return OptionGroupOutput(
            slug=group.slug,
            name=group.name,
            selection_mode=group.selection_mode,
            required=group.required,
            display_style=group.display_style,
            options=[self._option(option) for option in group.options],
        )

    def _option(self, option: Option) -> OptionOutput:
        return OptionOutput(
            slug=option.slug,
            name=option.name,
            price_delta_cents=option.price_delta_cents,
            description=option.description,
            layer=_layer(option.layer),
            swatch=_asset(option.swatch),
            model_effect=_model_effect(option.model_effect),
        )

    # The catalog is read-only over HTTP: it is loaded from the versioned seed/catalog.yaml, and
    # there is no create or update request to map from. Declared rather than deleted because
    # BaseMapper requires them and BaseService builds the full CRUD set -- but not faked, because
    # scaffolding that lies about being exercised is worse than scaffolding that admits it.
    def to_domain(self, create_request) -> Platform:  # pragma: no cover - read-only module
        raise NotImplementedError("the catalog is seeded from seed/catalog.yaml, not created")

    def to_update(self, entity: Platform, update_request) -> Platform:  # pragma: no cover
        raise NotImplementedError("the catalog is seeded from seed/catalog.yaml, not edited")
