"""A fixed-memory sliding-window rate limiter. Pure: no ``fastapi`` or ``sqlmodel`` imports.

Deliberately in-process. The API runs as a single small service and the thing being limited is
form submission, where the cost of an occasional miss after a restart or across two machines is
one extra lead to delete. The upgrade path is a shared Redis counter, at which point only this
module changes.
"""

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RateLimitVerdict:
    allowed: bool
    retry_after_seconds: int = 0


@dataclass
class RateLimiter:
    """At most ``limit`` hits per ``window_seconds`` for a given key."""

    limit: int
    window_seconds: float
    _hits: dict[str, deque[float]] = field(default_factory=dict, repr=False)

    def check(self, key: str, now: float | None = None) -> RateLimitVerdict:
        """Record a hit for ``key`` and say whether it is allowed.

        A rejected hit is *not* recorded: a client that keeps hammering should become allowed
        again once its earliest recorded hit ages out, rather than extending its own ban.
        """
        now = time.monotonic() if now is None else now
        self._evict(now)

        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window_seconds:
            hits.popleft()

        if len(hits) >= self.limit:
            retry_after = self.window_seconds - (now - hits[0])
            return RateLimitVerdict(allowed=False, retry_after_seconds=max(1, int(retry_after) + 1))

        hits.append(now)
        return RateLimitVerdict(allowed=True)

    def reset(self) -> None:
        self._hits.clear()

    def _evict(self, now: float) -> None:
        """Drop keys whose whole window has passed, so an unbounded number of distinct IPs
        cannot grow the map without bound."""
        stale = [
            key
            for key, hits in self._hits.items()
            if not hits or now - hits[-1] >= self.window_seconds
        ]
        for key in stale:
            del self._hits[key]
