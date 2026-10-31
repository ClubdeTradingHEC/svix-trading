"""
Unit Tests for the Analytics Module.
Validates the constant maturity variance interpolation.
"""

import pytest

from src.analytics import VarianceCalculator

interpolate = VarianceCalculator._interpolate_constant_maturity


def test_interpolation_example() -> None:
    """Checks the 23d / 37d example against the hand calculation."""
    assert interpolate(0.04, 23, 0.0625, 37) == pytest.approx(0.053875)


def test_equal_variances() -> None:
    """Equal variances on both maturities must return that same variance."""
    assert interpolate(0.04, 23, 0.04, 37) == pytest.approx(0.04)


def test_near_term_at_target() -> None:
    """If the near-term maturity is already 30 days, it must return its own variance."""
    assert interpolate(0.04, 30, 0.0625, 37) == pytest.approx(0.04)


def test_same_maturities_raises() -> None:
    """Identical maturities must raise a clear error instead of dividing by zero."""
    with pytest.raises(ValueError, match="must differ"):
        interpolate(0.04, 30, 0.0625, 30)
