"""Shared test fixtures loaded from the repo-root pricing fixture and the seed catalog."""

import json
from pathlib import Path

import pytest
import yaml

# api/ on the host, but /srv inside the container (see docker-compose.yml) -- computed relative
# to this file's own location so it resolves correctly in both.
API_ROOT = Path(__file__).resolve().parent.parent

# fixtures/ lives at the repo root, outside both api/ and web/ (see .claude/skills/pricing-mirror).
# The container only bind-mounts ./api, so docker-compose.yml separately mounts ./fixtures to
# API_ROOT/fixtures; on the host, the repo root is simply API_ROOT's parent.
_FIXTURES_CANDIDATES = [API_ROOT.parent / "fixtures", API_ROOT / "fixtures"]
FIXTURES_ROOT = next(path for path in _FIXTURES_CANDIDATES if path.exists())


@pytest.fixture(scope="session")
def catalog_yaml() -> dict:
    with (API_ROOT / "seed" / "catalog.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def pricing_cases() -> list[dict]:
    with (FIXTURES_ROOT / "pricing-cases.json").open() as f:
        return json.load(f)["cases"]


def platform_by_slug(catalog_yaml: dict, slug: str) -> dict:
    for platform in catalog_yaml["platforms"]:
        if platform["slug"] == slug:
            return platform
    raise KeyError(f"no platform with slug {slug!r}")


def rules_for_platform(catalog_yaml: dict, platform_slug: str) -> list[dict]:
    """Rules apply to whichever options they name; a platform only sees the ones whose
    subject option it actually has."""
    platform = platform_by_slug(catalog_yaml, platform_slug)
    option_slugs = {
        option["slug"] for group in platform["option_groups"] for option in group["options"]
    }
    return [rule for rule in catalog_yaml["rules"] if rule["subject"] in option_slugs]
