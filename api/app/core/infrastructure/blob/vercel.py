"""``IBlobStore`` over Vercel Blob's HTTP API.

Selected by ``app/assets.py`` whenever ``BLOB_READ_WRITE_TOKEN`` is set. No Vercel function sits
in the byte path: this PUTs straight from an operator's machine to ``blob.vercel-storage.com``,
which is the whole reason ``python -m app.assets sync`` is a CLI and not an upload endpoint --
see Stage 15 of the archived development plan (Notion). Not exercised by the test suite, which runs entirely
against ``LocalBlobStore``; docs/deploy.md covers creating the store and setting the token.
"""

import httpx

from app.core.config import Settings
from app.core.domain.interfaces import IBlobStore, StoredBlob

BASE_URL = "https://blob.vercel-storage.com"
TIMEOUT_SECONDS = 30.0

# Safe only because every path this service uploads to is content-addressed (the sha256 of the
# bytes, truncated -- see SyncModelsUseCase): the bytes at a given path never change, so a client
# caching the response forever is correct rather than merely convenient.
CACHE_CONTROL = "public, max-age=31536000, immutable"


class VercelBlobStore(IBlobStore):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.blob_read_write_token}"}

    def put(self, path: str, data: bytes, content_type: str) -> StoredBlob:
        response = httpx.put(
            f"{BASE_URL}/{path}",
            content=data,
            headers={
                **self._headers(),
                "content-type": content_type,
                "cache-control": CACHE_CONTROL,
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        url = response.json()["url"]
        return StoredBlob(url=url, path=path, byte_size=len(data))

    def delete(self, path: str) -> None:
        response = httpx.delete(
            BASE_URL,
            params={"url": f"{BASE_URL}/{path}"},
            headers=self._headers(),
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    def exists(self, path: str) -> bool:
        response = httpx.head(
            f"{BASE_URL}/{path}", headers=self._headers(), timeout=TIMEOUT_SECONDS
        )
        return response.status_code == 200
