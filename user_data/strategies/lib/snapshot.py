"""Market data snapshot cache with staleness detection.

Separates data collection (runs in background/populate_indicators) from
evaluation (runs in confirm_trade_entry). Callbacks read immutable snapshots
and fail closed when data is stale or missing.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    """Immutable market data snapshot with timestamp."""

    pair: str
    ticker: dict[str, Any] | None
    orderbook: dict[str, Any] | None
    timestamp: float
    error: str | None = None

    def is_stale(self, ttl_seconds: float = 60.0) -> bool:
        """Check if snapshot is older than TTL."""
        age = time.time() - self.timestamp
        return age > ttl_seconds

    def is_valid(self, ttl_seconds: float = 60.0) -> bool:
        """Snapshot is valid if not stale, no error, and has required data."""
        if self.is_stale(ttl_seconds):
            return False
        if self.error is not None:
            return False
        if self.ticker is None or self.orderbook is None:
            return False
        return True


class SnapshotCache:
    """Thread-safe market data cache with TTL."""

    def __init__(self, default_ttl: float = 60.0):
        self._cache: dict[str, MarketSnapshot] = {}
        self.default_ttl = default_ttl
        self._deny_reasons: dict[str, int] = {}

    def update(
        self,
        pair: str,
        ticker: dict[str, Any] | None = None,
        orderbook: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Update snapshot for a pair. Called by collector."""
        snapshot = MarketSnapshot(
            pair=pair,
            ticker=ticker,
            orderbook=orderbook,
            timestamp=time.time(),
            error=error,
        )
        self._cache[pair] = snapshot

    def get(self, pair: str, ttl_seconds: float | None = None) -> MarketSnapshot | None:
        """Get snapshot for pair. Returns None if missing."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        snapshot = self._cache.get(pair)
        if snapshot is None:
            return None
        if snapshot.is_stale(ttl):
            return None
        return snapshot

    def is_valid(self, pair: str, ttl_seconds: float | None = None) -> bool:
        """Check if pair has valid snapshot."""
        snapshot = self.get(pair, ttl_seconds)
        if snapshot is None:
            return False
        return snapshot.is_valid(ttl_seconds or self.default_ttl)

    def record_deny(self, pair: str, reason: str) -> None:
        """Record a deny reason for metrics/healthcheck."""
        key = f"{pair}:{reason}"
        self._deny_reasons[key] = self._deny_reasons.get(key, 0) + 1

    def get_deny_stats(self) -> dict[str, int]:
        """Get denial statistics for observability."""
        return dict(self._deny_reasons)

    def clear_stats(self) -> None:
        """Clear denial statistics."""
        self._deny_reasons.clear()


# Global cache instance - strategies share this cache
_global_cache = SnapshotCache(default_ttl=60.0)


def get_cache() -> SnapshotCache:
    """Get the global snapshot cache."""
    return _global_cache


def collect_market_snapshot(
    data_provider: Any,
    pair: str,
    orderbook_depth: int = 10,
) -> None:
    """Collect market data and update cache.

    Call this from populate_indicators or a background task, NOT from
    confirm_trade_entry. Captures exceptions and records errors.

    Args:
        data_provider: Freqtrade DataProvider instance
        pair: Trading pair to collect
        orderbook_depth: Order book depth to fetch
    """
    cache = get_cache()

    ticker_getter = getattr(data_provider, "ticker", None)
    orderbook_getter = getattr(data_provider, "orderbook", None)

    if not callable(ticker_getter) or not callable(orderbook_getter):
        cache.update(pair, error="data_provider_unavailable")
        return

    try:
        ticker = ticker_getter(pair)
        orderbook = orderbook_getter(pair, orderbook_depth)
        cache.update(pair, ticker=ticker, orderbook=orderbook)
    except Exception as e:
        logger.warning("Failed to collect snapshot for %s: %s", pair, e)
        cache.update(pair, error=f"collection_failed: {type(e).__name__}")
