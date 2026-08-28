"""The catalog's use cases, with no database anywhere.

This is what the ports bought. ``IPlatformRepository`` and ``ICacheInvalidator`` are filled with
a dictionary and a list here, so the decisions these classes make -- a missing slug is a 404 and
not a ``None``, an unnamed set of tags means every tag the catalog touches -- are checked without
a Postgres to seed or an HTTP client to drive.
"""

# `list` is a method on IPlatformRepository, so it shadows the builtin inside any class body
# implementing it -- `list[str]` in a later annotation would resolve to the method. See the
# note on IPlatformRepository.
from __future__ import annotations

import pytest

from app.modules.catalog.application.services import CatalogService
from app.modules.catalog.application.use_cases import (
    GetPlatformUseCase,
    RevalidateCatalogUseCase,
    SeedCatalogUseCase,
)
from app.modules.catalog.domain.exceptions import PlatformNotFoundError
from app.modules.catalog.domain.filters import PlatformFilter
from app.modules.catalog.domain.interfaces import (
    ICacheInvalidator,
    IPlatformRepository,
    RevalidateResult,
)
from app.modules.catalog.domain.models import Option, OptionGroup, Platform


def _platform(slug: str) -> Platform:
    return Platform(
        id=1,
        slug=slug,
        name=slug.title(),
        purpose="overland",
        chassis_basis="test",
        base_price_cents=100_00,
        option_groups=[
            OptionGroup(
                slug="g",
                name="Group",
                selection_mode="single",
                display_style="card",
                options=[Option(slug="a", name="A", price_delta_cents=10_00)],
            )
        ],
    )


class FakePlatforms(IPlatformRepository):
    def __init__(self, platforms: list[Platform]) -> None:
        self.platforms = platforms
        self.upsert_calls: list[dict] = []

    def upsert_from_catalog(self, catalog: dict) -> list[str]:
        self.upsert_calls.append(catalog)
        return [p["slug"] for p in catalog["platforms"]]

    def list(self, filters: PlatformFilter) -> list[Platform]:
        if filters.slug_eq is not None:
            return [p for p in self.platforms if p.slug == filters.slug_eq]
        return list(self.platforms)

    def by_slug(self, slug: str) -> Platform | None:
        found = self.list(PlatformFilter(slug_eq=slug))
        return found[0] if found else None

    def slugs(self) -> list[str]:
        return [p.slug for p in self.platforms]

    def create(self, entity):  # pragma: no cover - the catalog is seeded, not written
        raise NotImplementedError

    def count(self, filters):  # pragma: no cover - nothing paginates the catalog
        raise NotImplementedError

    def update(self, entity):  # pragma: no cover
        raise NotImplementedError

    def delete(self, entity):  # pragma: no cover
        raise NotImplementedError


class FakeInvalidator(ICacheInvalidator):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def invalidate(self, tags) -> RevalidateResult:
        tags = list(tags)
        self.calls.append(tags)
        return RevalidateResult(ok=True, tags=tuple(tags), detail="fake")


def _service(platforms: list[Platform]) -> tuple[CatalogService, FakeInvalidator]:
    invalidator = FakeInvalidator()
    return (
        CatalogService(repository=FakePlatforms(platforms), invalidator=invalidator),
        invalidator,
    )


def test_the_catalog_comes_back_in_one_envelope() -> None:
    service, _ = _service([_platform("bristlecone"), _platform("ironwood")])
    catalog = service.get_catalog()

    assert [platform.slug for platform in catalog.platforms] == ["bristlecone", "ironwood"]
    assert catalog.platforms[0].option_groups[0].options[0].slug == "a"


def test_a_missing_slug_is_a_404_not_a_none() -> None:
    """Returning ``None`` would push the decision to every caller, and one of them eventually
    forgets and serializes it as ``null`` with a 200."""
    service, _ = _service([_platform("bristlecone")])

    with pytest.raises(PlatformNotFoundError) as raised:
        service.get_platform("not-a-real-platform")

    assert raised.value.status_code == 404
    assert raised.value.code == "unknown_platform"
    assert "not-a-real-platform" in raised.value.message


def test_named_tags_are_sent_as_named() -> None:
    service, invalidator = _service([_platform("bristlecone")])
    result = service.revalidate(["platform-bristlecone"])

    assert result.ok
    assert invalidator.calls == [["platform-bristlecone"]]


def test_no_tags_means_everything_the_catalog_touches() -> None:
    """The right default for "I changed something, I am not certain what it reaches" -- and the
    reason the use case holds the repository as well as the invalidator."""
    service, invalidator = _service([_platform("bristlecone"), _platform("ironwood")])
    service.revalidate(None)

    assert invalidator.calls == [["catalog", "platform-bristlecone", "platform-ironwood"]]


def test_an_empty_tag_list_is_not_the_same_as_no_tags() -> None:
    """``[]`` is "revalidate nothing", ``None`` is "I don't know what changed". Collapsing the
    two would make an explicit empty request quietly drop every cache entry the site has."""
    service, invalidator = _service([_platform("bristlecone")])
    service.revalidate([])

    assert invalidator.calls == [[]]


def test_the_use_cases_can_be_built_without_a_service() -> None:
    """Nothing about these needs the wiring -- which is the property that makes them testable."""
    platforms = FakePlatforms([_platform("bristlecone")])

    get_platform = GetPlatformUseCase(filter_class=PlatformFilter, repository=platforms)
    assert get_platform.run(PlatformFilter(slug_eq="bristlecone")).slug == "bristlecone"

    invalidator = FakeInvalidator()
    revalidate = RevalidateCatalogUseCase(invalidator=invalidator, repository=platforms)
    assert revalidate.exec().tags == ("catalog", "platform-bristlecone")


def _catalog_dict(*slugs: str) -> dict:
    return {"platforms": [{"slug": slug} for slug in slugs], "rules": []}


def test_seeding_upserts_through_the_repository_and_returns_its_slugs() -> None:
    platforms = FakePlatforms([])
    invalidator = FakeInvalidator()
    seed = SeedCatalogUseCase(repository=platforms, invalidator=invalidator)

    catalog = _catalog_dict("bristlecone", "ironwood")
    slugs = seed.exec(catalog)

    assert slugs == ["bristlecone", "ironwood"]
    assert platforms.upsert_calls == [catalog]


def test_seeding_revalidates_the_slugs_it_just_wrote() -> None:
    platforms = FakePlatforms([])
    invalidator = FakeInvalidator()
    seed = SeedCatalogUseCase(repository=platforms, invalidator=invalidator)

    seed.exec(_catalog_dict("bristlecone"))

    assert invalidator.calls == [["catalog", "platform-bristlecone"]]


def test_no_revalidate_skips_the_invalidator_entirely() -> None:
    platforms = FakePlatforms([])
    invalidator = FakeInvalidator()
    seed = SeedCatalogUseCase(repository=platforms, invalidator=invalidator)

    seed.exec(_catalog_dict("bristlecone"), revalidate=False)

    assert invalidator.calls == []
