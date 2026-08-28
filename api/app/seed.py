"""Loads seed/catalog.yaml into Postgres, upserting by slug so re-running is always safe.

A thin CLI over the catalog module: read the YAML (``catalog/infrastructure/catalog_file.py``),
build the repository and cache-invalidator adapters directly -- there is no FastAPI request here
to hang a ``Depends`` off -- and hand both to ``SeedCatalogUseCase``
(``catalog/application/use_cases.py``), which does the upsert and the revalidation. Run with
``python -m app.seed``.

This is a second entrypoint into the same modules ``app/main.py`` assembles for HTTP, which is
why it names an adapter directly rather than going through ``CatalogService``: nothing about
seeding is a web concern.

Pass ``--no-revalidate`` where there is no web app to tell (CI, a database being prepared ahead of
a deploy); it is opt-out rather than opt-in because a stale public price is the costlier mistake.
"""

import argparse
import logging

from sqlmodel import Session

from app.core.config import get_settings
from app.core.infrastructure.postgres.database import engine
from app.modules.catalog.application.use_cases import SeedCatalogUseCase
from app.modules.catalog.infrastructure.catalog_file import read_catalog
from app.modules.catalog.infrastructure.postgres.repositories import PlatformRepositoryPostgres
from app.modules.catalog.infrastructure.webhook.revalidate import WebhookCacheInvalidator

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-revalidate",
        action="store_true",
        help="skip the web app cache revalidation (no web app to tell, e.g. in CI)",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    catalog = read_catalog()

    with Session(engine) as session:
        use_case = SeedCatalogUseCase(
            repository=PlatformRepositoryPostgres(session),
            invalidator=WebhookCacheInvalidator(settings),
        )
        slugs = use_case.exec(catalog, revalidate=not args.no_revalidate)

    logger.info("seeded %d platform(s): %s", len(slugs), ", ".join(slugs))
    if args.no_revalidate:
        logger.info("skipping cache revalidation (--no-revalidate)")


if __name__ == "__main__":
    main()
