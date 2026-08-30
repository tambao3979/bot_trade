"""Tests for market snapshot cache."""

import time
from unittest.mock import Mock

import pytest

from user_data.strategies.lib.snapshot import (
    MarketSnapshot,
    SnapshotCache,
    collect_market_snapshot,
    get_cache,
)


class TestMarketSnapshot:
    def test_snapshot_valid_when_fresh(self):
        snapshot = MarketSnapshot(
            pair="BTC/USDT",
            ticker={"bid": 50000, "ask": 50100},
            orderbook={"bids": [[50000, 1]], "asks": [[50100, 1]]},
            timestamp=time.time(),
            error=None,
        )
        assert snapshot.is_valid(ttl_seconds=60.0)
        assert not snapshot.is_stale(ttl_seconds=60.0)

    def test_snapshot_stale_when_old(self):
        snapshot = MarketSnapshot(
            pair="BTC/USDT",
            ticker={"bid": 50000, "ask": 50100},
            orderbook={"bids": [[50000, 1]], "asks": [[50100, 1]]},
            timestamp=time.time() - 120,  # 2 minutes ago
            error=None,
        )
        assert snapshot.is_stale(ttl_seconds=60.0)
        assert not snapshot.is_valid(ttl_seconds=60.0)

    def test_snapshot_invalid_with_error(self):
        snapshot = MarketSnapshot(
            pair="BTC/USDT",
            ticker=None,
            orderbook=None,
            timestamp=time.time(),
            error="exchange_down",
        )
        assert not snapshot.is_valid(ttl_seconds=60.0)

    def test_snapshot_invalid_with_missing_data(self):
        snapshot = MarketSnapshot(
            pair="BTC/USDT",
            ticker=None,
            orderbook={"bids": [[50000, 1]], "asks": [[50100, 1]]},
            timestamp=time.time(),
            error=None,
        )
        assert not snapshot.is_valid(ttl_seconds=60.0)


class TestSnapshotCache:
    def test_cache_stores_and_retrieves(self):
        cache = SnapshotCache(default_ttl=60.0)
        ticker = {"bid": 50000, "ask": 50100}
        orderbook = {"bids": [[50000, 1]], "asks": [[50100, 1]]}

        cache.update("BTC/USDT", ticker=ticker, orderbook=orderbook)
        snapshot = cache.get("BTC/USDT")

        assert snapshot is not None
        assert snapshot.pair == "BTC/USDT"
        assert snapshot.ticker == ticker
        assert snapshot.orderbook == orderbook
        assert snapshot.error is None

    def test_cache_returns_none_for_missing_pair(self):
        cache = SnapshotCache(default_ttl=60.0)
        assert cache.get("UNKNOWN/USDT") is None

    def test_cache_returns_none_for_stale_data(self):
        cache = SnapshotCache(default_ttl=1.0)
        cache.update("BTC/USDT", ticker={"bid": 50000}, orderbook={"bids": []})
        time.sleep(1.5)
        assert cache.get("BTC/USDT") is None

    def test_cache_validates_snapshot(self):
        cache = SnapshotCache(default_ttl=60.0)
        cache.update("BTC/USDT", ticker={"bid": 50000}, orderbook={"bids": []})
        assert cache.is_valid("BTC/USDT")

        cache.update("ETH/USDT", error="exchange_error")
        assert not cache.is_valid("ETH/USDT")

    def test_cache_records_deny_reasons(self):
        cache = SnapshotCache(default_ttl=60.0)
        cache.record_deny("BTC/USDT", "spread_too_wide")
        cache.record_deny("BTC/USDT", "spread_too_wide")
        cache.record_deny("ETH/USDT", "liquidity_low")

        stats = cache.get_deny_stats()
        assert stats["BTC/USDT:spread_too_wide"] == 2
        assert stats["ETH/USDT:liquidity_low"] == 1

    def test_cache_clears_stats(self):
        cache = SnapshotCache(default_ttl=60.0)
        cache.record_deny("BTC/USDT", "test")
        cache.clear_stats()
        assert cache.get_deny_stats() == {}


class TestCollectMarketSnapshot:
    def test_collect_updates_cache_with_valid_data(self):
        cache = get_cache()
        cache._cache.clear()  # Clear global cache

        dp = Mock()
        ticker = {"bid": 50000, "ask": 50100, "fundingRate": 0.0001}
        orderbook = {"bids": [[50000, 1]], "asks": [[50100, 1]]}
        dp.ticker.return_value = ticker
        dp.orderbook.return_value = orderbook

        collect_market_snapshot(dp, "BTC/USDT", orderbook_depth=10)

        snapshot = cache.get("BTC/USDT")
        assert snapshot is not None
        assert snapshot.ticker == ticker
        assert snapshot.orderbook == orderbook
        assert snapshot.error is None

    def test_collect_handles_exception(self):
        cache = get_cache()
        cache._cache.clear()

        dp = Mock()
        dp.ticker.side_effect = Exception("Network error")

        collect_market_snapshot(dp, "BTC/USDT")

        snapshot = cache.get("BTC/USDT")
        assert snapshot is not None
        assert snapshot.error is not None
        assert "Exception" in snapshot.error

    def test_collect_handles_missing_data_provider(self):
        cache = get_cache()
        cache._cache.clear()

        dp = Mock()
        del dp.ticker  # Missing ticker method

        collect_market_snapshot(dp, "BTC/USDT")

        snapshot = cache.get("BTC/USDT")
        assert snapshot is not None
        assert snapshot.error == "data_provider_unavailable"


class TestSnapshotIntegration:
    """Integration tests for snapshot cache with BaseRiskStrategy."""

    def test_snapshot_prevents_network_call_in_callback(self):
        """Verify confirm_trade_entry doesn't call network APIs."""
        from user_data.strategies.base.BaseRiskStrategy import BaseRiskStrategy

        # Create strategy with mocked config
        config = {"runmode": "dry_run"}
        strategy = BaseRiskStrategy(config)

        # Mock the data provider to raise if called
        dp = Mock()
        dp.ticker.side_effect = AssertionError("Network call in callback!")
        dp.orderbook.side_effect = AssertionError("Network call in callback!")
        strategy.dp = dp

        # Pre-populate cache with valid snapshot
        cache = strategy._snapshot_cache
        cache.update(
            "BTC/USDT",
            ticker={"bid": 50000, "ask": 50100, "quoteVolume": 10_000_000, "fundingRate": 0.0001},
            orderbook={
                "bids": [[50000, 10], [49990, 20]],
                "asks": [[50100, 10], [50110, 20]],
            },
        )

        # Mock equity for circuit breaker
        strategy.wallets = Mock()
        strategy.wallets.get_total_stake_amount.return_value = 10000

        # Call confirm_trade_entry - should NOT trigger network calls
        from datetime import UTC, datetime

        result = strategy.confirm_trade_entry(
            pair="BTC/USDT",
            order_type="limit",
            amount=0.1,
            rate=50100,
            time_in_force="GTC",
            current_time=datetime.now(UTC),
            entry_tag="test",
            side="long",
        )

        # If we get here without AssertionError, network calls were avoided
        assert isinstance(result, bool)
        # dp.ticker should NOT have been called
        dp.ticker.assert_not_called()
        dp.orderbook.assert_not_called()

    def test_stale_snapshot_rejects_entry(self):
        """Verify stale snapshots cause rejection."""
        from user_data.strategies.base.BaseRiskStrategy import BaseRiskStrategy

        config = {"runmode": "dry_run"}
        strategy = BaseRiskStrategy(config)
        strategy._snapshot_ttl = 1.0  # 1 second TTL

        # Clear stats from previous tests
        cache = strategy._snapshot_cache
        cache.clear_stats()

        # Add snapshot
        cache.update(
            "BTC/USDT",
            ticker={"bid": 50000, "ask": 50100, "quoteVolume": 10_000_000, "fundingRate": 0.0001},
            orderbook={"bids": [[50000, 10]], "asks": [[50100, 10]]},
        )

        time.sleep(1.5)  # Make it stale

        from datetime import UTC, datetime

        result = strategy.confirm_trade_entry(
            pair="BTC/USDT",
            order_type="limit",
            amount=0.1,
            rate=50100,
            time_in_force="GTC",
            current_time=datetime.now(UTC),
            entry_tag="test",
            side="long",
        )

        assert result is False
        # Stale snapshots are filtered by cache.get() and appear as "missing"
        stats = cache.get_deny_stats()
        assert any("snapshot_missing" in key for key in stats)
