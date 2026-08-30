"""
Tests for BaseRiskStrategy.custom_stake_amount (T09).
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pandas as pd

from user_data.strategies.base.BaseRiskStrategy import BaseRiskStrategy
from user_data.strategies.lib.indicators import atr


def _strategy_with_dp():
    strategy = BaseRiskStrategy()
    strategy.dp = MagicMock()
    # Simulate analyzed dataframe
    dates = pd.date_range("2020-01-01", periods=30, freq="15min")
    df = pd.DataFrame(
        {
            "date": dates,
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "volume": 1000,
        }
    )
    df["atr14"] = atr(df, 14)
    strategy.dp.get_analyzed_dataframe.return_value = (df, None)
    strategy.wallets = MagicMock()
    strategy.wallets.get_total_stake_amount.return_value = 1000
    return strategy


def test_custom_stake_basic():
    strategy = _strategy_with_dp()
    stake = strategy.custom_stake_amount(
        pair="BTC/USDC:USDC",
        current_time=datetime.now(UTC),
        current_rate=100,
        proposed_stake=20,
        min_stake=None,
        max_stake=200,
        leverage=1,
        entry_tag="test",
        side="long",
    )
    assert stake > 0


def test_custom_stake_max_cap():
    strategy = _strategy_with_dp()
    # very low ATR should trigger max cap
    strategy.dp.get_analyzed_dataframe.return_value = (
        pd.DataFrame(
            {
                "date": pd.date_range("2020-01-01", periods=30, freq="15min"),
                "open": 100,
                "high": 100.0001,
                "low": 99.9999,
                "close": 100,
                "volume": 1,
            }
        ),
        None,
    )
    strategy.wallets.get_total_stake_amount.return_value = 1000
    stake = strategy.custom_stake_amount(
        pair="BTC/USDC:USDC",
        current_time=datetime.now(UTC),
        current_rate=100,
        proposed_stake=20,
        min_stake=None,
        max_stake=200,
        leverage=1,
        entry_tag="test",
        side="long",
    )
    assert stake <= 250  # 1000 * 0.25
