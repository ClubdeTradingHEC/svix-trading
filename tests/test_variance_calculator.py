"""
Unit Tests for the Analytics Module.
Validates the constant maturity interpolation and the variance integration.
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from src.analytics import VarianceCalculator
from src.core.schemas import OptionChain

interpolate = VarianceCalculator._interpolate_constant_maturity
integrate = VarianceCalculator._integrate_variance


# ==========================================
# Interpolation Tests
# ==========================================


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


# ==========================================
# Integration Tests (Black-Scholes market)
# ==========================================

S0, R, SIGMA, DAYS = 4000.0, 0.05, 0.20, 30
T = DAYS / 365


def _make_bs_chain() -> tuple[pd.DataFrame, OptionChain]:
    """Builds a fake OTM option surface priced with Black-Scholes at 20% vol."""
    f = S0 * np.exp(R * T)
    k = np.arange(2000, 8001, 5)
    d1 = (np.log(S0 / k) + (R + SIGMA**2 / 2) * T) / (SIGMA * np.sqrt(T))
    d2 = d1 - SIGMA * np.sqrt(T)
    call = S0 * norm.cdf(d1) - k * np.exp(-R * T) * norm.cdf(d2)
    put = k * np.exp(-R * T) * norm.cdf(-d2) - S0 * norm.cdf(-d1)
    price = np.where(k < f, put, call)

    otm = pd.DataFrame({"strike": k, "option_type": np.where(k < f, "P", "C"), "bid": price, "ask": price, "mid_price": price})
    chain = OptionChain(
        date=datetime(2026, 11, 1), maturity_days=DAYS, underlying_price=S0, risk_free_rate=R, forward_price=f, options_data=otm
    )
    return otm, chain


def test_vix_recovers_black_scholes_vol() -> None:
    """In a Black-Scholes market, VIX^2 must equal sigma^2."""
    otm, chain = _make_bs_chain()
    assert integrate(otm, chain, is_svix=False) == pytest.approx(SIGMA**2, rel=1e-3)


def test_svix_matches_martin_theory() -> None:
    """In a Black-Scholes market, SVIX^2 must equal (exp(sigma^2 T) - 1) / T."""
    otm, chain = _make_bs_chain()
    expected = (np.exp(SIGMA**2 * T) - 1) / T
    assert integrate(otm, chain, is_svix=True) == pytest.approx(expected, rel=1e-3)


def test_svix_above_vix() -> None:
    """In a Black-Scholes market, SVIX^2 must be slightly above VIX^2."""
    otm, chain = _make_bs_chain()
    assert integrate(otm, chain, is_svix=True) > integrate(otm, chain, is_svix=False)
