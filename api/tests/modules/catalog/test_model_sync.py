"""``SyncModelsUseCase``, with no database and a real ``LocalBlobStore`` writing to a temp dir.

The point of the whole stage is the last test here: a catalog naming a node or material its
platform's GLB does not actually contain must fail the sync by construction, because nothing else
would catch it -- the option would still price, still appear in the build sheet, and do nothing
on screen. See Stage 15 of the archived development plan (Notion).

``LocalBlobStore`` rather than a fake: it is itself the adapter ``docker compose``, CI and
``python -m app.assets sync`` fall back to whenever ``BLOB_READ_WRITE_TOKEN`` is unset, so
exercising it here is exercising real behaviour, not a stand-in for it -- the same reasoning
``tests/modules/quotes/test_submit_quote.py`` gives for testing against a fake mailer that is
itself a supported configuration.
"""

import hashlib
import json
import struct

import pytest

from app.assets import _read_candidate
from app.core.infrastructure.blob.local import LocalBlobStore
from app.modules.catalog.application.use_cases import ModelCandidate, SyncModelsUseCase
from app.modules.catalog.domain.enums import DisplayStyle, SelectionMode
from app.modules.catalog.domain.exceptions import (
    InvalidModelFileError,
    ModelContentMismatchError,
    ModelTooLargeError,
)
from app.modules.catalog.domain.filters import PlatformFilter
from app.modules.catalog.domain.interfaces import ICacheInvalidator, IPlatformRepository
from app.modules.catalog.domain.models import (
    BuildModel,
    Option,
    OptionGroup,
    OptionModelEffect,
    Platform,
)


def _glb_bytes(nodes: list[str], materials: list[str]) -> bytes:
    """A GLB needs no geometry to be a valid one -- a header plus a JSON chunk naming the nodes
    and materials Stage 15 cares about is enough."""
    document = {
        "asset": {"version": "2.0"},
        "nodes": [{"name": name} for name in nodes],
        "materials": [{"name": name} for name in materials],
    }
    chunk_data = json.dumps(document).encode("utf-8")
    chunk_data += b" " * ((4 - len(chunk_data) % 4) % 4)  # glTF chunks are 4-byte aligned

    chunk_header = struct.pack("<I4s", len(chunk_data), b"JSON")
    total_length = 12 + len(chunk_header) + len(chunk_data)
    header = struct.pack("<4sII", b"glTF", 2, total_length)
    return header + chunk_header + chunk_data


def _candidate(platform_slug: str, nodes: list[str], materials: list[str]) -> ModelCandidate:
    data = _glb_bytes(nodes, materials)
    return ModelCandidate(
        platform_slug=platform_slug,
        filename=f"{platform_slug}.glb",
        data=data,
        content_hash=hashlib.sha256(data).hexdigest(),
        byte_size=len(data),
        nodes=frozenset(nodes),
        materials=frozenset(materials),
    )


def _model(content_hash: str = "") -> BuildModel:
    return BuildModel(
        content_hash=content_hash,
        alt_text="Bristlecone, 3D build model",
        camera_orbit_deg=35,
        camera_distance_m=9.5,
        camera_target_y_m=1.6,
    )


def _platform(model: BuildModel | None) -> Platform:
    return Platform(
        id=1,
        slug="bristlecone",
        name="Bristlecone",
        purpose="expedition",
        chassis_basis="test",
        base_price_cents=100_00,
        model=model,
        option_groups=[
            OptionGroup(
                slug="cab-chassis",
                name="Cab & Chassis",
                selection_mode=SelectionMode.single,
                display_style=DisplayStyle.card,
                options=[
                    Option(
                        slug="cab-crew",
                        name="Crew cab",
                        model_effect=OptionModelEffect(nodes=["cab_crew"]),
                    ),
                    Option(
                        slug="satin-black",
                        name="Satin black",
                        model_effect=OptionModelEffect(material_target="body_paint"),
                    ),
                ],
            )
        ],
    )


class FakePlatforms(IPlatformRepository):
    """A dictionary the fake write mutates, so a second ``exec`` against the same instance sees
    the reference the first one wrote -- what makes the "second sync is a no-op" test real."""

    def __init__(self, platforms: list[Platform]) -> None:
        self.platforms = {platform.slug: platform for platform in platforms}
        self.model_writes: list[tuple[str, str, str, int]] = []

    def by_slug(self, slug: str) -> Platform | None:
        return self.platforms.get(slug)

    def slugs(self) -> list[str]:
        return list(self.platforms)

    def write_model_reference(self, slug: str, url: str, content_hash: str, byte_size: int) -> None:
        self.model_writes.append((slug, url, content_hash, byte_size))
        platform = self.platforms[slug]
        updated_model = platform.model.model_copy(
            update={"url": url, "content_hash": content_hash, "byte_size": byte_size}
        )
        self.platforms[slug] = platform.model_copy(update={"model": updated_model})

    def list(self, filters: PlatformFilter):  # pragma: no cover - not reached from here
        raise NotImplementedError

    def upsert_from_catalog(self, catalog: dict):  # pragma: no cover - not reached from here
        raise NotImplementedError

    def create(self, entity):  # pragma: no cover
        raise NotImplementedError

    def count(self, filters):  # pragma: no cover
        raise NotImplementedError

    def update(self, entity):  # pragma: no cover
        raise NotImplementedError

    def delete(self, entity):  # pragma: no cover
        raise NotImplementedError


class FakeInvalidator(ICacheInvalidator):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def invalidate(self, tags):
        self.calls.append(list(tags))
        return None  # never read by the use case


def _use_case(
    repository: FakePlatforms, invalidator: FakeInvalidator, tmp_path
) -> SyncModelsUseCase:
    return SyncModelsUseCase(
        repository=repository,
        invalidator=invalidator,
        blob_store=LocalBlobStore(base_dir=tmp_path),
        blob_path_prefix="models",
    )


def test_a_first_sync_uploads_and_writes_the_reference(tmp_path) -> None:
    repository = FakePlatforms([_platform(_model())])
    invalidator = FakeInvalidator()
    candidate = _candidate("bristlecone", ["cab_crew"], ["body_paint"])

    records = _use_case(repository, invalidator, tmp_path).exec([candidate])

    assert len(records) == 1
    record = records[0]
    assert record.platform_slug == "bristlecone"
    assert record.status == "uploaded"
    assert record.byte_size == candidate.byte_size

    assert repository.model_writes == [
        ("bristlecone", record.url, candidate.content_hash, candidate.byte_size)
    ]
    assert (tmp_path / "models" / "bristlecone" / f"{candidate.content_hash[:16]}.glb").exists()
    assert invalidator.calls == [["catalog", "platform-bristlecone"]]


def test_a_second_sync_uploads_nothing_and_writes_nothing(tmp_path) -> None:
    repository = FakePlatforms([_platform(_model())])
    invalidator = FakeInvalidator()
    candidate = _candidate("bristlecone", ["cab_crew"], ["body_paint"])
    use_case = _use_case(repository, invalidator, tmp_path)

    use_case.exec([candidate])
    records = use_case.exec([candidate])

    assert records[0].status == "unchanged"
    assert len(repository.model_writes) == 1  # still just the first sync's write
    assert invalidator.calls == [["catalog", "platform-bristlecone"]]  # not called a second time


def test_dry_run_reports_without_writing(tmp_path) -> None:
    repository = FakePlatforms([_platform(_model())])
    invalidator = FakeInvalidator()
    candidate = _candidate("bristlecone", ["cab_crew"], ["body_paint"])

    records = _use_case(repository, invalidator, tmp_path).exec([candidate], dry_run=True)

    assert records[0].status == "would-upload"
    assert repository.model_writes == []
    assert invalidator.calls == []
    assert not (tmp_path / "models").exists()


def test_a_file_over_the_size_cap_is_refused(tmp_path) -> None:
    path = tmp_path / "bristlecone.glb"
    path.write_bytes(_glb_bytes(["cab_crew"], ["body_paint"]))

    with pytest.raises(ModelTooLargeError):
        _read_candidate(path, max_bytes=8)


def test_a_file_without_the_gltf_magic_is_refused(tmp_path) -> None:
    path = tmp_path / "bristlecone.glb"
    path.write_bytes(b"not a glb, just some bytes")

    with pytest.raises(InvalidModelFileError):
        _read_candidate(path, max_bytes=1_000_000)


def test_a_catalog_naming_a_node_the_glb_does_not_contain_fails_the_sync(tmp_path) -> None:
    """The one that justifies the stage: without this, a node renamed in Blender is an option
    that still prices, still appears in the build sheet, and does nothing on screen -- and no
    other test would fail."""
    repository = FakePlatforms([_platform(_model())])
    invalidator = FakeInvalidator()
    # The GLB names neither "cab_crew" nor "body_paint", which the catalog's two options require.
    candidate = _candidate("bristlecone", ["some_other_node"], [])

    with pytest.raises(ModelContentMismatchError) as raised:
        _use_case(repository, invalidator, tmp_path).exec([candidate])

    assert "cab-crew" in raised.value.message
    assert "cab_crew" in raised.value.message
    assert "bristlecone.glb" in raised.value.message
    assert repository.model_writes == []
    assert invalidator.calls == []
