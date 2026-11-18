import math
from datetime import datetime

import pandas as pd
import pytest

from src.data.wrds_loader import WRDSOptionLoader


def _make_raw_surface() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cp_flag": ["C", "C", "P", "P", "C", "P", "C"],
            "strike_price": [
                5_000_000,
                5_100_000,
                4_900_000,
                4_800_000,
                5_200_000,
                4_700_000,
                5_300_000,
            ],
            "best_bid": [50.0, 0.0, 40.0, 10.0, 20.0, 5.0, 10.0],
            "best_offer": [52.0, 1.0, 42.0, 9.0, 21.0, 5.0, 11.0],
            "volume": [100, 50, 0, 10, 0, 50, 5],
            "open_interest": [1000, 500, 200, 100, 0, 500, 8],
        }
    )


def _make_expiry_rows(exdate: str, maturity: int, am_settlement: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "exdate": [exdate, exdate],
            "maturity_days": [maturity, maturity],
            "cp_flag": ["P", "C"],
            "strike_price": [4_900_000, 5_100_000],
            "best_bid": [10.0, 12.0],
            "best_offer": [11.0, 13.0],
            "volume": [100, 100],
            "open_interest": [1000, 1000],
            "am_settlement": [am_settlement, am_settlement],
        }
    )


def _make_offline_loader(raw: pd.DataFrame) -> WRDSOptionLoader:
    """Builds a loader without a WRDS connection, with stubbed data access."""
    loader = WRDSOptionLoader.__new__(WRDSOptionLoader)  # skips __init__ (no WRDS)
    loader._query_raw_surface = lambda date, min_maturity, max_maturity: raw
    loader._extract_macro_state = lambda date, target_maturity: (5000.0, 0.04, 0.01, 5010.0)
    return loader


def test_filters_remove_invalid_quotes():
    clean = WRDSOptionLoader._apply_quantitative_filters(_make_raw_surface())
    # Kept: the valid call, and the put with open interest but no volume.
    # Removed: zero bid, crossed quote (ask < bid), locked quote (ask == bid),
    # no activity, and activity below the liquidity thresholds.
    assert len(clean) == 2
    assert (clean["bid"] > 0).all()
    assert (clean["ask"] > clean["bid"]).all()
    assert 4700.0 not in clean["strike"].values  # locked quote removed
    assert 5300.0 not in clean["strike"].values  # illiquid option removed


def test_filters_standardize_strike_and_mid_price():
    clean = WRDSOptionLoader._apply_quantitative_filters(_make_raw_surface())
    call = clean[clean["option_type"] == "C"].iloc[0]
    assert call["strike"] == 5000.0
    assert call["mid_price"] == 51.0


def test_select_settlement_series_prefers_pm_when_both_exist():
    raw = pd.concat(
        [
            _make_expiry_rows("2025-03-21", 18, 1.0),  # AM-settled SPX
            _make_expiry_rows("2025-03-21", 18, 0.0),  # PM-settled SPXW, same expiry
            _make_expiry_rows("2025-04-17", 45, 1.0),  # AM-settled only
        ]
    )
    selected = WRDSOptionLoader._select_settlement_series(raw)
    assert (selected[selected["exdate"] == "2025-03-21"]["am_settlement"] == 0).all()
    assert len(selected[selected["exdate"] == "2025-04-17"]) == 2


def test_get_interpolation_chains_brackets_target_maturity():
    raw = pd.concat(
        [
            _make_expiry_rows("2025-03-28", 25, 0.0),
            _make_expiry_rows("2025-04-01", 29, 0.0),
            _make_expiry_rows("2025-04-04", 32, 0.0),
            _make_expiry_rows("2025-04-04", 32, 1.0),  # duplicate series, must be dropped
            _make_expiry_rows("2025-04-12", 40, 0.0),
        ]
    )
    chains = _make_offline_loader(raw).get_interpolation_chains(datetime(2025, 3, 3), target_days=30)

    assert [chain.maturity_days for chain in chains] == [29.0, 32.0]
    assert len(chains[1].options_data) == 2  # no double counting
    assert chains[0].forward_price == 5010.0
    assert "mid_price" in chains[0].options_data.columns


def test_get_interpolation_chains_raises_without_bracket():
    raw = _make_expiry_rows("2025-04-04", 32, 0.0)  # nothing below 30 days
    with pytest.raises(ValueError):
        _make_offline_loader(raw).get_interpolation_chains(datetime(2025, 3, 3), target_days=30)


def test_interpolate_rate_is_linear_and_in_decimal():
    curve = pd.DataFrame({"days": [10.0, 30.0], "rate": [4.0, 5.0]})
    assert math.isclose(WRDSOptionLoader._interpolate_rate(curve, 20.0), 0.045)


def test_forward_price_formula():
    forward = WRDSOptionLoader._forward_price(100.0, 0.05, 0.01, 365.0)
    assert math.isclose(forward, 100.0 * math.exp(0.04))
