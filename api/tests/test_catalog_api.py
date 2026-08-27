"""Contract tests for the catalog endpoints, run against the seeded Postgres database (see the
stage 1 checkpoint: migrate, seed, then run this suite)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_catalog_returns_the_three_seed_platforms() -> None:
    response = client.get("/v1/catalog")
    assert response.status_code == 200
    slugs = [platform["slug"] for platform in response.json()["platforms"]]
    assert slugs == ["bristlecone", "ironwood", "sentinel"]


def test_get_catalog_sends_etag_and_cache_control() -> None:
    response = client.get("/v1/catalog")
    assert response.headers["cache-control"]
    assert response.headers["etag"]


def test_get_catalog_returns_304_for_matching_etag() -> None:
    first = client.get("/v1/catalog")
    second = client.get("/v1/catalog", headers={"if-none-match": first.headers["etag"]})
    assert second.status_code == 304


def test_get_catalog_includes_the_seed_rules() -> None:
    response = client.get("/v1/catalog")
    bristlecone = next(p for p in response.json()["platforms"] if p["slug"] == "bristlecone")
    rules = {(r["subject"], r["relation"], r["object"]) for r in bristlecone["rules"]}
    assert ("winch-12000", "requires", "bumper-heavy") in rules
    assert ("lithium-600ah", "excludes", "galley-compact") in rules
    assert ("rooftop-tent", "excludes", "solar-max") in rules


def test_get_platform_by_slug_returns_nested_shape() -> None:
    response = client.get("/v1/platforms/bristlecone")
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "bristlecone"
    assert body["base_price_cents"] == 21_450_000
    group_slugs = [group["slug"] for group in body["option_groups"]]
    assert "power-system" in group_slugs
    assert body["hero_image"]["url"]


def test_get_platform_carries_the_viewer_composite() -> None:
    """The configurator viewer stacks the platform base layer plus one layer per selected
    option; an option with nothing to show contributes ``null`` rather than being omitted."""
    body = client.get("/v1/platforms/bristlecone").json()
    assert body["viewer_base"]["url"] == "/images/bristlecone/viewer/base.png"
    assert body["viewer_base"]["z_index"] == 0

    options = {o["slug"]: o for group in body["option_groups"] for o in group["options"]}
    assert options["rooftop-tent"]["layer"]["url"] == "/images/bristlecone/viewer/rooftop-tent.png"
    assert options["rooftop-tent"]["layer"]["z_index"] == 46
    assert options["galley-full"]["layer"] is None


def test_get_platform_carries_swatches_for_swatch_groups() -> None:
    body = client.get("/v1/platforms/bristlecone").json()
    finishes = next(g for g in body["option_groups"] if g["display_style"] == "swatch")
    assert all(option["swatch"]["url"] for option in finishes["options"])


def test_get_platform_by_slug_sends_etag_and_cache_control() -> None:
    response = client.get("/v1/platforms/bristlecone")
    assert response.headers["cache-control"]
    assert response.headers["etag"]


def test_get_platform_unknown_slug_is_404() -> None:
    response = client.get("/v1/platforms/not-a-real-platform")
    assert response.status_code == 404
