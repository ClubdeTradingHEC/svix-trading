"""
Unit Tests for the Analytics Module.
Validates the constant maturity interpolation and the variance integration.
"""

import json
from datetime import datetime
from pathlib import Path

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


# ==========================================
# OTM Isolation Tests (Données « dummy »)
# ==========================================

DATA_DIR = Path(__file__).parent / "data"


def _load_dummy_chain() -> OptionChain:
    """Loads the dummy SPX chain (one call and one put per strike) from tests/data."""
    df = pd.read_csv(DATA_DIR / "dummy_spx_chain.csv")
    ctx = json.loads((DATA_DIR / "dummy_spx_context.json").read_text())
    ctx["date"] = datetime.fromisoformat(ctx["date"])
    return OptionChain(**ctx, options_data=df)


def test_isolate_splits_at_forward() -> None:
    """Puts must be strictly below the forward, calls at or above it."""
    chain = _load_dummy_chain()
    otm = VarianceCalculator._isolate_otm_options(chain)
    assert (otm[otm["option_type"] == "P"]["strike"] < chain.forward_price).all()
    assert (otm[otm["option_type"] == "C"]["strike"] >= chain.forward_price).all()


def test_isolate_one_option_per_strike_sorted() -> None:
    """The OTM surface must contain one option per strike, sorted by strike."""
    otm = VarianceCalculator._isolate_otm_options(_load_dummy_chain())
    assert otm["strike"].is_unique
    assert otm["strike"].is_monotonic_increasing


# ==========================================
# Full Pipeline Tests (compute_metrics)
# ==========================================


def _make_full_bs_chain(days: float) -> OptionChain:
    """Builds a full Black-Scholes chain (one call and one put per strike) at 20 % vol."""
    t = days / 365
    f = S0 * np.exp(R * t)
    k = np.arange(2000, 8001, 5).astype(float)
    d1 = (np.log(S0 / k) + (R + SIGMA**2 / 2) * t) / (SIGMA * np.sqrt(t))
    d2 = d1 - SIGMA * np.sqrt(t)
    call = S0 * norm.cdf(d1) - k * np.exp(-R * t) * norm.cdf(d2)
    put = k * np.exp(-R * t) * norm.cdf(-d2) - S0 * norm.cdf(-d1)

    options = pd.DataFrame(
        {
            "strike": np.concatenate([k, k]),
            "option_type": ["C"] * len(k) + ["P"] * len(k),
            "mid_price": np.concatenate([call, put]),
        }
    )
    options["bid"] = options["mid_price"]
    options["ask"] = options["mid_price"]
    return OptionChain(datetime(2026, 11, 1), days, S0, R, f, options)


def test_compute_metrics_recovers_black_scholes_vol() -> None:
    """With two Black-Scholes chains at 20 % vol, the 30-day VIX must be 20 % and the SVIX slightly above."""
    metrics = VarianceCalculator().compute_metrics([_make_full_bs_chain(23), _make_full_bs_chain(37)])
    assert metrics.maturity_days == 30
    assert metrics.is_interpolated
    assert metrics.vix_annualized == pytest.approx(SIGMA, rel=1e-3)
    assert metrics.svix_annualized > metrics.vix_annualized


def test_compute_metrics_chain_order_does_not_matter() -> None:
    """Passing the chains in reverse order must give the same result."""
    calc = VarianceCalculator()
    a = calc.compute_metrics([_make_full_bs_chain(23), _make_full_bs_chain(37)])
    b = calc.compute_metrics([_make_full_bs_chain(37), _make_full_bs_chain(23)])
    assert a.vix_annualized == pytest.approx(b.vix_annualized)
    assert a.svix_annualized == pytest.approx(b.svix_annualized)


def test_compute_metrics_requires_two_chains() -> None:
    """Anything other than exactly two chains must be rejected."""
    with pytest.raises(ValueError, match="exactly 2 chains"):
        VarianceCalculator().compute_metrics([_make_full_bs_chain(30)])
