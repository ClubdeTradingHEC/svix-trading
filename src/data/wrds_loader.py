"""
WRDS Data Engineering Pipeline.
Handles database connections,
raw SQL queries, and volatility surface micro-structure filtering.
"""

from datetime import datetime
from typing import List, Tuple

import pandas as pd

from src.core.schemas import OptionChain

# OptionMetrics column names -> OptionChain contract column names.
# TODO: align with the field names defined in src/core/schemas.py
_OPTIONMETRICS_COLUMN_MAP = {
    "cp_flag": "option_type",
    "strike_price": "strike",
    "best_bid": "bid",
    "best_offer": "ask",
}


class WRDSOptionLoader:
    """
    Data integration layer for OptionMetrics via WRDS.
    Extracts, cleans, and packages SPX option chains into strictly validated contracts.
    """

    def __init__(self) -> None:
        """
        Initializes the loader and the database connection.
        """
        self._connection = None
        raise NotImplementedError("Nizar: Implement the wrds.Connection() logic here.")

    def _query_raw_surface(self, date: datetime, min_maturity: int, max_maturity: int) -> pd.DataFrame:
        """
        Executes the raw SQL query to OptionMetrics (opprcd, secprd, zerocd tables).

        Args:
            date (datetime): The target historical date.
            min_maturity (int): Minimum days to maturity.
            max_maturity (int): Maximum days to maturity.

        Returns:
            pd.DataFrame: Unfiltered, raw WRDS dataframe.
        """
        raise NotImplementedError("Nizar: Write the raw WRDS SQL query here.")

    @staticmethod
    def _apply_quantitative_filters(raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        Cleans the option surface based on quantitative microstructure rules.

        Rules implemented:
        1. Remove zero or negative bids.
        2. Remove options with neither volume nor open interest.
        3. Remove crossed quotes (ask < bid).
           TODO: put-call parity bounds once the forward price is available.
        4. Standardize column names to match the OptionChain contract.

        Args:
            raw_df (pd.DataFrame): The raw dataframe from WRDS.

        Returns:
            pd.DataFrame: The cleaned surface ready for Analytics.
        """
        df = raw_df.copy()

        # 1. Zero or negative bids (NaN bids are dropped as well)
        df = df[df["best_bid"] > 0]

        # 2. No trading activity at all
        df = df[(df["volume"] > 0) | (df["open_interest"] > 0)]

        # 3. Crossed quotes
        df = df[df["best_offer"] >= df["best_bid"]]

        # 4. Standardization (OptionMetrics stores strikes multiplied by 1000)
        df["strike_price"] = df["strike_price"] / 1000.0
        df["mid"] = (df["best_bid"] + df["best_offer"]) / 2.0
        df = df.rename(columns=_OPTIONMETRICS_COLUMN_MAP)

        return df.sort_values(["option_type", "strike"]).reset_index(drop=True)

    def _extract_macro_state(self, date: datetime, target_maturity: float) -> Tuple[float, float, float, float]:
        """
        Retrieves the underlying market state for a specific date and maturity.

        Args:
            date (datetime): Target date.
            target_maturity (float): Target maturity in days.

        Returns:
            Tuple[float, float, float, float]: (underlying_price, risk_free_rate, dividend_yield, forward_price)
        """
        raise NotImplementedError("Nizar: Extract S, r, q from WRDS tables and compute the theoretical Forward Price (F).")

    def get_interpolation_chains(self, date: datetime, target_days: int = 30) -> List[OptionChain]:
        """
        Fetches the two option chains bracketing the target maturity.
        Required by the Analytics module for constant-maturity interpolation (e.g., 30-day VIX).

        Args:
            date (datetime): The target historical date.
            target_days (int): The constant maturity target (default: 30).

        Returns:
            List[OptionChain]: A list containing exactly two OptionChain contracts
                               (the nearest sub-30 maturity and the nearest post-30 maturity).
        """
        # Architectural guidance for Nizar:
        # 1. Query surface between target_days - 15 and target_days + 15
        # 2. Identify the closest maturities T1 < target_days and T2 >= target_days
        # 3. Clean the data using _apply_quantitative_filters
        # 4. Extract macro state for T1 and T2
        # 5. Package and return [OptionChain(T1), OptionChain(T2)]

        raise NotImplementedError("Nizar: Implement the bracketing logic and return the instantiated contracts.")
