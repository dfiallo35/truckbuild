"""Uploads model GLBs to Blob and writes their references into Postgres.

Reads ``api/seed/models/<platform-slug>.glb`` -- gitignored, since these are large binaries and
``seed/catalog.yaml`` stays the reviewable text half of the seed. A thin CLI over the catalog
module, on the model of ``app/seed.py``: build the adapters directly -- there is no FastAPI
request here to hang a ``Depends`` off -- and hand them to ``SyncModelsUseCase``
(``catalog/application/use_cases.py``), which validates, uploads and writes.

A CLI and not an upload endpoint, deliberately: a Vercel function caps a request body at 4.5 MB
and these files run 5-50 MB. This PUTs straight from an operator's machine to
``blob.vercel-storage.com``, so no Vercel function is ever in the byte path. See
docs/stages/15-blob-storage-ingest.md.

Run with ``python -m app.assets sync``, the same way ``python -m app.seed`` is run -- from a
machine with the direct Neon URL and, here, ``BLOB_READ_WRITE_TOKEN``. ``--dry-run`` reports what
would upload and writes nothing; ``--no-revalidate`` skips telling the web app, for the same
reason ``app/seed.py`` has the same flag.
"""

import argparse
import hashlib
import logging
import sys
from pathlib import Path

from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.domain.exceptions import BaseError
from app.core.domain.interfaces import IBlobStore
from app.core.infrastructure.blob.local import LocalBlobStore
from app.core.infrastructure.blob.vercel import VercelBlobStore
from app.core.infrastructure.postgres.database import engine
from app.modules.catalog.application.use_cases import ModelCandidate, SyncModelsUseCase
from app.modules.catalog.domain.exceptions import ModelTooLargeError
from app.modules.catalog.infrastructure.glb import read_glb
from app.modules.catalog.infrastructure.postgres.repositories import PlatformRepositoryPostgres
from app.modules.catalog.infrastructure.webhook.revalidate import WebhookCacheInvalidator

logger = logging.getLogger(__name__)

# api/app/assets.py -> parents[1] is api/
MODELS_DIR = Path(__file__).resolve().parents[1] / "seed" / "models"


def _read_candidate(path: Path, max_bytes: int) -> ModelCandidate:
    data = path.read_bytes()
    byte_size = len(data)
    if byte_size > max_bytes:
        raise ModelTooLargeError(path.name, byte_size, max_bytes)

    contents = read_glb(data, path.name)
    return ModelCandidate(
        platform_slug=path.stem,
        filename=path.name,
        data=data,
        content_hash=hashlib.sha256(data).hexdigest(),
        byte_size=byte_size,
        nodes=contents.nodes,
        materials=contents.materials,
    )


def _blob_store(settings: Settings) -> IBlobStore:
    if settings.blob_read_write_token:
        return VercelBlobStore(settings)
    return LocalBlobStore()


def _sync(args: argparse.Namespace, settings: Settings) -> None:
    if not MODELS_DIR.exists() or not any(MODELS_DIR.glob("*.glb")):
        logger.info("no .glb files in seed/models/ -- nothing to sync")
        return

    paths = sorted(MODELS_DIR.glob("*.glb"))
    try:
        candidates = [_read_candidate(path, settings.model_max_bytes) for path in paths]
    except BaseError as exc:
        logger.error("refusing to sync: %s", exc.message)
        sys.exit(1)

    with Session(engine) as session:
        use_case = SyncModelsUseCase(
            repository=PlatformRepositoryPostgres(session),
            invalidator=WebhookCacheInvalidator(settings),
            blob_store=_blob_store(settings),
            blob_path_prefix=settings.blob_path_prefix,
        )
        try:
            records = use_case.exec(
                candidates, dry_run=args.dry_run, revalidate=not args.no_revalidate
            )
        except BaseError as exc:
            logger.error("refusing to sync: %s", exc.message)
            sys.exit(1)

    for record in records:
        logger.info(
            "%s: %s (%s, %d bytes)",
            record.platform_slug,
            record.status,
            record.url,
            record.byte_size,
        )
    if args.no_revalidate:
        logger.info("skipping cache revalidation (--no-revalidate)")


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser(
        "sync", help="upload changed models, write their references"
    )
    sync_parser.add_argument(
        "--dry-run", action="store_true", help="report what would sync, write nothing"
    )
    sync_parser.add_argument(
        "--no-revalidate",
        action="store_true",
        help="skip the web app cache revalidation (no web app to tell, e.g. in CI)",
    )

    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "sync":
        _sync(args, settings)


if __name__ == "__main__":
    main()
