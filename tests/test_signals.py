from datetime import datetime

import pytest

from src.core.schemas import VolatilityMetrics
from src.signals.signal_generator import SignalGenerator


def test_derive_target_weight():
    generator = SignalGenerator()

    # Standard SVIX value
    assert generator._derive_target_weight(0.20) == pytest.approx(0.02)

    # Zero volatility
    assert generator._derive_target_weight(0.0) == 0.0

    # Allocation capped at 100%
    assert generator._derive_target_weight(2.0) == 1.0


def test_generate_signals():
    generator = SignalGenerator()

    metrics = VolatilityMetrics(
        date=datetime(2026, 9, 25),
        maturity_days=30.0,
        is_interpolated=True,
        underlying_price=5000.0,
        risk_free_rate=0.05,
        dividend_yield=0.01,
        svix_annualized=0.20,
        vix_annualized=0.25,
        min_strike_used=4500.0,
        max_strike_used=5500.0,
        integration_points=100,
    )

    signals = generator.generate_signals([metrics])

    # Verify signal generation and allocation
    assert len(signals) == 1
    assert signals[0].target_weight == pytest.approx(0.02)

    # Verify next business day execution (Friday to Monday)
    assert signals[0].signal_date == datetime(2026, 9, 25)
    assert signals[0].target_execution_date == datetime(2026, 9, 28)

    # Verify market data propagation
    assert signals[0].underlying_price_at_signal == 5000.0
    assert signals[0].risk_free_rate == 0.05
    assert signals[0].dividend_yield == 0.01
