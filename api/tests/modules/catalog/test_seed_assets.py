"""Every image path in the seed catalog must have a file behind it in ``web/public``.

Stage 3 shipped seed URLs with nothing behind them and every ``next/image`` 404'd, which only
surfaced by eye. The seed content is checked against the files here instead.
"""

from pathlib import Path

import pytest

from tests.conftest import API_ROOT

WEB_PUBLIC = API_ROOT.parent / "web" / "public"


def _image_urls(catalog: dict) -> list[str]:
    urls: list[str] = []
    for platform in catalog["platforms"]:
        urls.append(platform["hero_image"]["url"])
        urls.extend(image["url"] for image in platform.get("gallery", []))
        for group in platform["option_groups"]:
            for option in group["options"]:
                if "swatch" in option:
                    urls.append(option["swatch"]["url"])
    return urls


def test_every_seed_image_url_has_a_file(catalog_yaml: dict) -> None:
    # web/ is not mounted into the API container; this check is a host/CI one.
    if not WEB_PUBLIC.is_dir():
        pytest.skip("web/public is not reachable from here")

    missing = [
        url for url in _image_urls(catalog_yaml) if not (WEB_PUBLIC / url.lstrip("/")).is_file()
    ]
    assert not missing, f"seed references images with no file: {sorted(missing)}"


def test_swatch_groups_give_every_option_a_swatch(catalog_yaml: dict) -> None:
    """A swatch group renders colour chips; an option without one would render an empty chip."""
    for platform in catalog_yaml["platforms"]:
        for group in platform["option_groups"]:
            if group["display_style"] != "swatch":
                continue
            for option in group["options"]:
                assert "swatch" in option, f"{option['slug']} is in a swatch group with no swatch"


def test_paths_that_look_like_files_are_absolute(catalog_yaml: dict) -> None:
    assert all(url.startswith("/") for url in _image_urls(catalog_yaml))


def test_web_public_holds_no_orphaned_swatch_images(catalog_yaml: dict) -> None:
    """The inverse check: art generated for an option that was later renamed or removed."""
    if not WEB_PUBLIC.is_dir():
        pytest.skip("web/public is not reachable from here")

    referenced = {(WEB_PUBLIC / url.lstrip("/")).resolve() for url in _image_urls(catalog_yaml)}
    on_disk = {
        path.resolve()
        for path in (WEB_PUBLIC / "images").rglob("*")
        if path.is_file() and Path(path).parent.name == "swatches"
    }
    assert not on_disk - referenced, f"unreferenced swatch art: {sorted(on_disk - referenced)}"
