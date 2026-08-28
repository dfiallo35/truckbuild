"""The YAML read, split out of ``app/seed.py`` in stage 13 -- infrastructure because it touches
a filesystem, and nothing else in the catalog module does.
"""

from app.modules.catalog.infrastructure.catalog_file import CATALOG_PATH, read_catalog


def test_read_catalog_defaults_to_the_versioned_seed_file() -> None:
    catalog = read_catalog()
    assert catalog["platforms"], "expected at least one platform in api/seed/catalog.yaml"
    assert "rules" in catalog


def test_catalog_path_points_at_the_versioned_seed_file() -> None:
    assert CATALOG_PATH.name == "catalog.yaml"
    assert CATALOG_PATH.parent.name == "seed"
    assert CATALOG_PATH.is_file()


def test_read_catalog_accepts_an_explicit_path(tmp_path) -> None:
    custom = tmp_path / "custom.yaml"
    custom.write_text("platforms: []\nrules: []\n")

    assert read_catalog(custom) == {"platforms": [], "rules": []}
