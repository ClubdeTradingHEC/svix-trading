"""
Guardrail Unit Tests for Core Data Contracts.
Validates instantiation logic, state immutability, and boundary enforcement.
"""

import importlib
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.core.schemas import OptionChain, TradeSignal, VolatilityMetrics


def test_architectural_module_imports() -> None:
    """Validates that all foundational modules are correctly registered in the Python path."""
    modules = [
        "src.core",
        "src.data",
        "src.analytics",
        "src.signals",
        "src.portfolio",
    ]
    for mod in modules:
        assert importlib.import_module(mod) is not None


# ==========================================
# TradeSignal Contract Tests
# ==========================================


def test_trade_signal_success() -> None:
    """Validates successful instantiation of a standard TradeSignal."""
    t_signal = datetime(2026, 9, 25, 16, 0)
    t_exec = t_signal + timedelta(days=1)

    signal = TradeSignal(
        signal_date=t_signal,
        target_execution_date=t_exec,
        underlying_price_at_signal=4000.0,
        target_weight=0.5,
        risk_free_rate=0.05,
        dividend_yield=0.01,
        signal_confidence=1.2,
    )

    assert signal.target_weight == 0.5
    assert signal.underlying_price_at_signal == 4000.0


def test_trade_signal_look_ahead_bias_prevention() -> None:
    """Proves that the contract actively rejects execution dates preceding or matching the signal date."""
    t_signal = datetime(2026, 9, 25, 16, 0)
    t_exec = datetime(2026, 9, 25, 15, 0)  # Execution happens BEFORE signal: Look-Ahead Bias

    with pytest.raises(ValueError, match="Look-ahead bias"):
        TradeSignal(
            signal_date=t_signal,
            target_execution_date=t_exec,
            underlying_price_at_signal=4000.0,
            target_weight=0.5,
            risk_free_rate=0.05,
            dividend_yield=0.01,
        )


def test_trade_signal_weight_boundaries() -> None:
    """Proves that portfolio target weights cannot exceed the [-1.0, 1.0] Delta-One mandate."""
    t_signal = datetime(2026, 9, 25, 16, 0)
    t_exec = t_signal + timedelta(days=1)

    # Upper bound violation
    with pytest.raises(ValueError, match="outside absolute bounds"):
        TradeSignal(t_signal, t_exec, 4000.0, 1.5, 0.05, 0.01)

    # Lower bound violation
    with pytest.raises(ValueError, match="outside absolute bounds"):
        TradeSignal(t_signal, t_exec, 4000.0, -1.1, 0.05, 0.01)


def test_trade_signal_nan_rejection() -> None:
    """Proves that numerical singularities (NaN or Inf) crash the pipeline immediately."""
    t_signal = datetime(2026, 9, 25, 16, 0)
    t_exec = t_signal + timedelta(days=1)

    # Corrected match pattern to align with schemas.py exception string
    with pytest.raises(ValueError, match="finite number"):
        TradeSignal(
            signal_date=t_signal,
            target_execution_date=t_exec,
            underlying_price_at_signal=4000.0,
            target_weight=np.nan,
            risk_free_rate=0.05,
            dividend_yield=0.01,
        )


# ==========================================
# OptionChain Contract Tests
# ==========================================


def test_option_chain_missing_columns() -> None:
    """Proves that the data pipeline halts if WRDS returns incomplete option columns."""
    df_incomplete = pd.DataFrame(
        {
            "strike": [4000],
            "option_type": ["C"],
            "bid": [10],
            # Missing 'ask' and 'mid_price'
        }
    )

    with pytest.raises(ValueError, match="Missing columns"):
        OptionChain(
            date=datetime(2026, 9, 25),
            maturity_days=30,
            underlying_price=4000.0,
            risk_free_rate=0.05,
            forward_price=4020.0,
            options_data=df_incomplete,
        )


# ==========================================
# VolatilityMetrics Contract Tests
# ==========================================


def test_volatility_metrics_negative_variance() -> None:
    """Proves that mathematical integration errors (yielding negative volatility) are caught."""
    with pytest.raises(ValueError, match="cannot be negative"):
        VolatilityMetrics(
            date=datetime(2026, 9, 25),
            maturity_days=30.0,
            is_interpolated=True,
            underlying_price=4000.0,
            risk_free_rate=0.05,
            dividend_yield=0.01,
            svix_annualized=-0.15,  # Impossible state
            vix_annualized=0.18,
            min_strike_used=3500.0,
            max_strike_used=4500.0,
            integration_points=100,
        )
