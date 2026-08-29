"""``IBlobStore`` over the local filesystem, writing under ``web/public/``.

Selected by ``app/assets.py`` whenever ``BLOB_READ_WRITE_TOKEN`` is unset -- which is what lets
docker compose, CI and the test suite run the whole sync with no cloud credential, the same
"works without the cloud" property ``tests/modules/quotes/test_submit_quote.py`` already has for
mail. ``web/public/<path>`` is where Next.js already serves static files from the site root, so
the path handed to ``put`` and the URL handed back are the same string with a leading slash.
"""

from pathlib import Path

from app.core.domain.interfaces import IBlobStore, StoredBlob

# api/app/core/infrastructure/blob/local.py -> parents[5] is the repo root
WEB_PUBLIC_DIR = Path(__file__).resolve().parents[5] / "web" / "public"


class LocalBlobStore(IBlobStore):
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or WEB_PUBLIC_DIR

    def put(self, path: str, data: bytes, content_type: str) -> StoredBlob:
        target = self.base_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return StoredBlob(url=f"/{path}", path=path, byte_size=len(data))

    def delete(self, path: str) -> None:
        (self.base_dir / path).unlink(missing_ok=True)

    def exists(self, path: str) -> bool:
        return (self.base_dir / path).exists()
