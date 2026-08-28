"""One catalog operation, one class. Hooks are overridden; ``exec`` is not, except where the
operation genuinely takes something other than an integer key.

Nothing here names a session, a query, ``HTTPException`` or a status code. What a caller cannot
have is raised as a ``BaseError`` from ``domain/exceptions.py`` and rendered by the handler
``core`` installs.
"""

from collections.abc import Iterable

from app.core.application.use_cases import BaseUseCase, GetByIdUseCase, ListUseCase
from app.modules.catalog.application.dtos import CatalogOutput, PlatformOutput
from app.modules.catalog.domain.cache_tags import tags_for_platforms
from app.modules.catalog.domain.exceptions import PlatformNotFoundError
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
