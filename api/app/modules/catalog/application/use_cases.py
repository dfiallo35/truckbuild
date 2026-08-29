"""One catalog operation, one class. Hooks are overridden; ``exec`` is not, except where the
operation genuinely takes something other than an integer key.

Nothing here names a session, a query, ``HTTPException`` or a status code. What a caller cannot
have is raised as a ``BaseError`` from ``domain/exceptions.py`` and rendered by the handler
``core`` installs.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from app.core.application.use_cases import BaseUseCase, GetByIdUseCase, ListUseCase
from app.core.domain.interfaces import IBlobStore
from app.modules.catalog.application.dtos import CatalogOutput, PlatformOutput
from app.modules.catalog.domain.cache_tags import tags_for_platforms
from app.modules.catalog.domain.exceptions import (
    ModelContentMismatchError,
    PlatformHasNoModelError,
    PlatformNotFoundError,
)
from app.modules.catalog.domain.filters import PlatformFilter
from app.modules.catalog.domain.interfaces import (
    ICacheInvalidator,
    IPlatformRepository,
    RevalidateResult,
)
from app.modules.catalog.domain.models import Platform


class GetCatalogUseCase(ListUseCase):
    """Every platform, fully loaded, in one envelope.

    Only ``get_output`` is overridden: the list, the filtering and the ordering are already what
    ``ListUseCase`` does, and ``{"platforms": [...]}`` is a shape the response takes rather than a
    step in the operation.
    """

    def get_output(self, entity: list[Platform]) -> CatalogOutput:
        return CatalogOutput(platforms=[self.mapper.to_api(platform) for platform in entity])


class GetPlatformUseCase(GetByIdUseCase):
    """One platform by slug, or a 404 -- never ``None``.

    ``exec`` is overridden rather than a hook because the identifier really is different: slugs
    are this service's public identifiers (they appear in URLs and shared builds) and the integer
    key is never serialized. The pipeline underneath is the inherited one.
    """

    def run(self, filters: PlatformFilter) -> Platform:
        platforms = self.repository.list(filters)
        if not platforms:
            raise PlatformNotFoundError(filters.slug_eq)
        return platforms[0]

    def exec(self, slug: str) -> PlatformOutput:
        filters = self.filter_class(slug_eq=slug)
        filters = self.pre_run(filters=filters)
        self.validate(filters=filters)
        platform = self.run(filters=filters)
        platform = self.post_run(filters=filters, entity=platform)
        return self.get_output(platform)


class RevalidateCatalogUseCase(BaseUseCase):
    """Drop the web app's cache tags for a catalog change.

    With no tags named it drops everything the catalog touches -- the right default for "I
    changed something, I am not certain what it reaches" -- which is why it holds the repository
    as well as the invalidator.

    The failure is *reported*, not raised: the tags either went or they did not, and the caller
    decides what that means. ``python -m app.seed`` logs it and carries on, because the catalog is
    already loaded; ``POST /v1/admin/revalidate`` answers 502, because an operator asked for this
    on purpose and a silent no-op leaves a wrong price on a public page.
    """

    def __init__(
        self,
        *args,
        invalidator: ICacheInvalidator | None = None,
        repository: IPlatformRepository | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, repository=repository, **kwargs)
        self.invalidator = invalidator

    def pre_run(self, tags: Iterable[str] | None) -> list[str]:
        if tags is not None:
            return list(tags)
        return tags_for_platforms(self.repository.slugs())

    def run(self, tags: list[str]) -> RevalidateResult:
        return self.invalidator.invalidate(tags)

    def post_run(self, tags: list[str], result: RevalidateResult) -> RevalidateResult:
        return result

    def exec(self, tags: Iterable[str] | None = None) -> RevalidateResult:
        tags = self.pre_run(tags)
        self.validate()
        result = self.run(tags)
        return self.post_run(tags, result)


class SeedCatalogUseCase(BaseUseCase):
    """Load a catalog dict into storage, upserting by slug, then tell the web app's cache.

    The one writer the catalog has. Built directly by ``app/seed.py`` rather than through
    ``CatalogService`` -- seeding is a second entrypoint into this module's own layers, not an
    HTTP concern, which is the point of keeping the wiring for it out of the service.
    """

    def __init__(
        self,
        *args,
        invalidator: ICacheInvalidator | None = None,
        repository: IPlatformRepository | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, repository=repository, **kwargs)
        self.invalidator = invalidator

    def pre_run(self, catalog: dict, revalidate: bool) -> dict:
        return catalog

    def validate(self, catalog: dict, revalidate: bool) -> None:
        pass

    def run(self, catalog: dict) -> list[str]:
        return self.repository.upsert_from_catalog(catalog)

    def post_run(self, slugs: list[str], revalidate: bool) -> list[str]:
        if revalidate:
            self.invalidator.invalidate(tags_for_platforms(slugs))
        return slugs

    def exec(self, catalog: dict, *, revalidate: bool = True) -> list[str]:
        catalog = self.pre_run(catalog, revalidate)
        self.validate(catalog, revalidate)
        slugs = self.run(catalog)
        return self.post_run(slugs, revalidate)


@dataclass(frozen=True)
class ModelCandidate:
    """One ``<platform-slug>.glb`` file, already read, hashed and parsed.

    Parsing a GLB is ``catalog/infrastructure/glb.py``'s job -- an adapter -- and ``application``
    may not import one (the layer contract in ``pyproject.toml``), so ``app/assets.py`` reads and
    parses each file and hands over exactly what ``SyncModelsUseCase`` needs to decide, the same
    division ``app/seed.py`` already draws with ``catalog_file.read_catalog``.
    """

    platform_slug: str
    filename: str
    data: bytes
    content_hash: str
    byte_size: int
    nodes: frozenset[str]
    materials: frozenset[str]


@dataclass(frozen=True)
class ModelSyncRecord:
    """What happened to one platform's model."""

    platform_slug: str
    status: str  # "uploaded" | "unchanged" | "would-upload"
    url: str
    byte_size: int


class SyncModelsUseCase(BaseUseCase):
    """Cross-checks every option's ``model_effect`` against what its platform's GLB actually
    contains, uploads whatever changed, and writes the reference back -- the one writer of
    ``BuildModel.url``/``content_hash``/``byte_size``. Built directly by ``app/assets.py``, the
    same way ``SeedCatalogUseCase`` is built by ``app/seed.py``: a CLI has no request to hang a
    ``Depends`` off.

    ``validate`` walks every candidate before ``run`` writes anything, so a mismatch on the third
    platform still leaves the first two untouched -- **the whole sync refuses**, not just the one
    platform. Without this check a node renamed in Blender is an option that still prices, still
    appears in the build sheet, and does nothing on screen, and no test would fail. See
    docs/stages/15-blob-storage-ingest.md.
    """

    def __init__(
        self,
        *args,
        blob_store: IBlobStore | None = None,
        invalidator: ICacheInvalidator | None = None,
        repository: IPlatformRepository | None = None,
        blob_path_prefix: str = "models",
        **kwargs,
    ) -> None:
        super().__init__(*args, repository=repository, **kwargs)
        self.blob_store = blob_store
        self.invalidator = invalidator
        self.blob_path_prefix = blob_path_prefix
        self._platforms: dict[str, Platform] = {}

    def pre_run(
        self, candidates: list[ModelCandidate], dry_run: bool, revalidate: bool
    ) -> list[ModelCandidate]:
        return candidates

    def validate(self, candidates: list[ModelCandidate], dry_run: bool, revalidate: bool) -> None:
        self._platforms = {}
        for candidate in candidates:
            platform = self.repository.by_slug(candidate.platform_slug)
            if platform is None:
                raise PlatformNotFoundError(candidate.platform_slug)
            if platform.model is None:
                raise PlatformHasNoModelError(candidate.platform_slug)
            self._platforms[candidate.platform_slug] = platform

            for option in platform.options:
                effect = option.model_effect
                if effect is None:
                    continue
                for node in effect.nodes:
                    if node not in candidate.nodes:
                        raise ModelContentMismatchError(
                            platform.slug, option.slug, "node", node, candidate.filename
                        )
                if (
                    effect.material_target is not None
                    and effect.material_target not in candidate.materials
                ):
                    raise ModelContentMismatchError(
                        platform.slug,
                        option.slug,
                        "material",
                        effect.material_target,
                        candidate.filename,
                    )

    def run(self, candidates: list[ModelCandidate], dry_run: bool) -> list[ModelSyncRecord]:
        records = []
        for candidate in candidates:
            existing = self._platforms[candidate.platform_slug].model

            if existing.content_hash == candidate.content_hash:
                records.append(
                    ModelSyncRecord(
                        platform_slug=candidate.platform_slug,
                        status="unchanged",
                        url=existing.url,
                        byte_size=existing.byte_size,
                    )
                )
                continue

            path = (
                f"{self.blob_path_prefix}/{candidate.platform_slug}/"
                f"{candidate.content_hash[:16]}.glb"
            )

            if dry_run:
                records.append(
                    ModelSyncRecord(
                        platform_slug=candidate.platform_slug,
                        status="would-upload",
                        url=path,
                        byte_size=candidate.byte_size,
                    )
                )
                continue

            stored = self.blob_store.put(path, candidate.data, "model/gltf-binary")
            self.repository.write_model_reference(
                candidate.platform_slug, stored.url, candidate.content_hash, stored.byte_size
            )
            records.append(
                ModelSyncRecord(
                    platform_slug=candidate.platform_slug,
                    status="uploaded",
                    url=stored.url,
                    byte_size=stored.byte_size,
                )
            )
        return records

    def post_run(self, records: list[ModelSyncRecord], revalidate: bool) -> list[ModelSyncRecord]:
        if revalidate:
            uploaded = [record.platform_slug for record in records if record.status == "uploaded"]
            if uploaded:
                self.invalidator.invalidate(tags_for_platforms(uploaded))
        return records

    def exec(
        self, candidates: list[ModelCandidate], *, dry_run: bool = False, revalidate: bool = True
    ) -> list[ModelSyncRecord]:
        candidates = self.pre_run(candidates, dry_run, revalidate)
        self.validate(candidates, dry_run, revalidate)
        records = self.run(candidates, dry_run)
        return self.post_run(records, revalidate)
