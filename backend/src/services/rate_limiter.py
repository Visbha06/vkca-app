"""Process-local sliding-window rate limiting for login failures."""

from collections.abc import Callable
from threading import RLock
from time import monotonic

DEFAULT_WINDOW_SECONDS = 15 * 60
CLEANUP_INTERVAL_SECONDS = 60


class InMemoryRateLimiter:
    """Track recent failures per key within a rolling time window."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        cleanup_interval_seconds: int = CLEANUP_INTERVAL_SECONDS,
    ) -> None:
        self._clock = clock
        self._cleanup_interval_seconds = cleanup_interval_seconds
        self._attempts: dict[str, list[float]] = {}
        self._last_cleanup = clock()
        self._lock = RLock()

    def sliding_window_check(
        self,
        key: str,
        max_attempts: int = 5,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> bool:
        """Return whether ``key`` has reached the rolling-window threshold."""

        now = self._clock()
        with self._lock:
            self._cleanup_if_due(now, window_seconds)
            attempts = self._prune_key(key, now, window_seconds)
            return len(attempts) >= max_attempts

    def record_failure(self, key: str) -> None:
        """Record one failed attempt for ``key`` at the current time."""

        now = self._clock()
        with self._lock:
            self._cleanup_if_due(now, DEFAULT_WINDOW_SECONDS)
            attempts = self._prune_key(key, now, DEFAULT_WINDOW_SECONDS)
            attempts.append(now)
            self._attempts[key] = attempts

    def record_success(self, key: str) -> None:
        """Reset all recent failures for a successfully authenticated key."""

        with self._lock:
            self._attempts.pop(key, None)

    def cleanup_expired(
        self,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        """Remove expired timestamps and empty keys from the limiter."""

        now = self._clock()
        with self._lock:
            self._cleanup_expired_unlocked(now, window_seconds)
            self._last_cleanup = now

    def attempt_count(
        self,
        key: str,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> int:
        """Return the active failure count for diagnostics and tests."""

        now = self._clock()
        with self._lock:
            return len(self._prune_key(key, now, window_seconds))

    def clear(self) -> None:
        """Clear all counters, primarily for process lifecycle and test isolation."""

        with self._lock:
            self._attempts.clear()
            self._last_cleanup = self._clock()

    def _cleanup_if_due(self, now: float, window_seconds: int) -> None:
        if now - self._last_cleanup < self._cleanup_interval_seconds:
            return
        self._cleanup_expired_unlocked(now, window_seconds)
        self._last_cleanup = now

    def _cleanup_expired_unlocked(self, now: float, window_seconds: int) -> None:
        for key in list(self._attempts):
            self._prune_key(key, now, window_seconds)

    def _prune_key(
        self,
        key: str,
        now: float,
        window_seconds: int,
    ) -> list[float]:
        cutoff = now - window_seconds
        active_attempts = [
            timestamp for timestamp in self._attempts.get(key, []) if timestamp > cutoff
        ]
        if active_attempts:
            self._attempts[key] = active_attempts
        else:
            self._attempts.pop(key, None)
        return active_attempts


rate_limiter = InMemoryRateLimiter()
