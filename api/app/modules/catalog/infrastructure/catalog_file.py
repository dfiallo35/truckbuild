"""Reads ``seed/catalog.yaml`` into a plain dict.

The one piece of loading the catalog that touches a filesystem rather than storage -- split out
so ``SeedCatalogUseCase`` (``catalog/application/use_cases.py``) never has to import ``yaml`` or
know where the file lives. ``app/seed.py`` is the only caller.
"""

from pathlib import Path

import yaml

# api/app/modules/catalog/infrastructure/catalog_file.py -> parents[4] is api/
CATALOG_PATH = Path(__file__).resolve().parents[4] / "seed" / "catalog.yaml"


def read_catalog(path: Path | None = None) -> dict:
    with (path or CATALOG_PATH).open() as f:
        return yaml.safe_load(f)
