"""``IBlobStore`` over Vercel Blob's HTTP API.

Selected by ``app/assets.py`` whenever ``BLOB_READ_WRITE_TOKEN`` is set. No Vercel function sits
in the byte path: this PUTs straight from an operator's machine to ``blob.vercel-storage.com``,
which is the whole reason ``python -m app.assets sync`` is a CLI and not an upload endpoint --
see Stage 15 of the archived development plan (Notion). Not exercised by the test suite, which
runs entirely against ``LocalBlobStore``; docs/deploy.md covers creating the store and setting
the token.
"""

import httpx

from app.core.config import Settings
from app.core.domain.interfaces import IBlobStore, StoredBlob

BASE_URL = "https://blob.vercel-storage.com"
# Connect and read stay short, so a dead endpoint or a hung response still fails fast. The write
# budget is the one that has to be generous: ``put`` streams the whole GLB in the request body,
# and this is the service that exists to move files docs/deploy.md sizes at 5-50 MB. A single
# 30 s budget covered all four phases, which was not enough to upload a 1.5 MB model on an
# ordinary uplink -- a sync got two platforms up and then raised ``httpx.WriteTimeout`` on the
# third, leaving the catalog half-updated and the cache never revalidated.
TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=600.0, pool=10.0)

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
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        url = response.json()["url"]
        return StoredBlob(url=url, path=path, byte_size=len(data))

    def delete(self, path: str) -> None:
        response = httpx.delete(
            BASE_URL,
            params={"url": f"{BASE_URL}/{path}"},
            headers=self._headers(),
            timeout=TIMEOUT,
        )
        response.raise_for_status()

    def exists(self, path: str) -> bool:
        response = httpx.head(f"{BASE_URL}/{path}", headers=self._headers(), timeout=TIMEOUT)
        return response.status_code == 200
