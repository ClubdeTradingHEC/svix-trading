import pandas as pd

from src.data.wrds_loader import WRDSOptionLoader


def _make_raw_surface() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cp_flag": ["C", "C", "P", "P", "C"],
            "strike_price": [5_000_000, 5_100_000, 4_900_000, 4_800_000, 5_200_000],
            "best_bid": [50.0, 0.0, 40.0, 10.0, 20.0],
            "best_offer": [52.0, 1.0, 42.0, 9.0, 21.0],
            "volume": [100, 50, 0, 10, 0],
            "open_interest": [1000, 500, 200, 100, 0],
        }
    )


def test_filters_remove_invalid_quotes():
    clean = WRDSOptionLoader._apply_quantitative_filters(_make_raw_surface())
    # Kept: the valid call, and the put with open interest but no volume.
    # Removed: zero bid, crossed quote, no activity.
    assert len(clean) == 2
    assert (clean["bid"] > 0).all()
    assert (clean["ask"] >= clean["bid"]).all()


def test_filters_standardize_strike_and_mid():
    clean = WRDSOptionLoader._apply_quantitative_filters(_make_raw_surface())
    call = clean[clean["option_type"] == "C"].iloc[0]
    assert call["strike"] == 5000.0
    assert call["mid"] == 51.0
