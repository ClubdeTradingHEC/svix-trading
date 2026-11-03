"""
WRDS Data Engineering Pipeline.
Handles database connections,
raw SQL queries, and volatility surface micro-structure filtering.
"""

import os
from datetime import datetime
from typing import List, Tuple

import pandas as pd
import wrds
from dotenv import load_dotenv

from src.core.schemas import OptionChain

# OptionMetrics security identifier of the S&P 500 index (SPX).
_SPX_SECID = 108105

# OptionMetrics column names -> OptionChain contract column names.
_OPTIONMETRICS_COLUMN_MAP = {
    "cp_flag": "option_type",
    "strike_price": "strike",
    "best_bid": "bid",
    "best_offer": "ask",
}

# Minimum liquidity thresholds: an option is kept if it reaches at least one of them.
_MIN_VOLUME = 10
_MIN_OPEN_INTEREST = 10


class WRDSOptionLoader:
    """
    Data integration layer for OptionMetrics via WRDS.
    Extracts, cleans, and packages SPX option chains into strictly validated contracts.
    """

    def __init__(self) -> None:
        """
        Initializes the loader and the database connection.
        Reads the WRDS username from the WRDS_USERNAME environment variable
        (loaded from the .env file at the project root).

        Raises:
            ValueError: If WRDS_USERNAME is not defined.
        """
        load_dotenv()
        username = os.getenv("WRDS_USERNAME")

        if not username:
            raise ValueError("WRDS_USERNAME is not set. Add it to your .env file.")

        self._connection = wrds.Connection(wrds_username=username)

    def _run_query(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        """
        Executes a SQL query on WRDS and returns the result as a DataFrame.

        Queries go through the underlying psycopg2 connection: wrds 3.1.6 pins
        SQLAlchemy 1.4, which pandas 3 no longer supports, so
        wrds.Connection.raw_sql fails with "'Connection' object has no attribute 'cursor'".

        Args:
            sql (str): The SQL query, with %(name)s placeholders for parameters.
            params (dict | None): Values for the query placeholders.

        Returns:
            pd.DataFrame: The query result.
        """
        raw_conn = self._connection.connection.connection
        try:
            with raw_conn.cursor() as cur:
                cur.execute(sql, params)
                columns = [col[0] for col in cur.description]
                return pd.DataFrame(cur.fetchall(), columns=columns)
        except Exception:
            raw_conn.rollback()  # reset the connection state after a failed query
            raise

    def _query_raw_surface(self, date: datetime, min_maturity: int, max_maturity: int) -> pd.DataFrame:
        """
        Executes the raw SQL query to OptionMetrics (opprcd table).

        Returns all SPX options quoted on the target date whose maturity lies between
        min_maturity and max_maturity days. Both AM-settled (SPX) and PM-settled (SPXW)
        series are returned, with am_settlement and expiry_indicator columns so that
        the series selection can be made downstream.

        Args:
            date (datetime): The target historical date.
            min_maturity (int): Minimum days to maturity.
            max_maturity (int): Maximum days to maturity.

        Returns:
            pd.DataFrame: Unfiltered, raw WRDS dataframe.
        """
        # OptionMetrics splits option prices into one table per year.
        # The table name is built from an integer year, so it is safe to format.
        table = f"optionm.opprcd{date.year}"
        sql = f"""
            SELECT
                date, exdate, (exdate - date) AS maturity_days,
                cp_flag, strike_price, best_bid, best_offer,
                volume, open_interest, impl_volatility,
                forward_price, am_settlement, expiry_indicator, root
            FROM {table}
            WHERE secid = %(secid)s
              AND date = %(date)s
              AND (exdate - date) BETWEEN %(min_m)s AND %(max_m)s
        """
        params = {
            "secid": _SPX_SECID,
            "date": pd.Timestamp(date).date(),
            "min_m": min_maturity,
            "max_m": max_maturity,
        }
        return self._run_query(sql, params)

    @staticmethod
    def _apply_quantitative_filters(raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        Cleans the option surface based on quantitative microstructure rules.

        Rules implemented:
        1. Remove zero or negative bids.
        2. Remove illiquid options: an option is kept only if its volume or its
           open interest reaches the minimum threshold (_MIN_VOLUME,
           _MIN_OPEN_INTEREST).
        3. Remove crossed (ask < bid) and locked (ask == bid) quotes:
           a valid market must always have a strictly positive spread.
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

        # 2. Illiquid options (neither traded nor held in sufficient size)
        df = df[(df["volume"] >= _MIN_VOLUME) | (df["open_interest"] >= _MIN_OPEN_INTEREST)]

        # 3. Crossed or locked quotes (strictly positive spread required)
        df = df[df["best_offer"] > df["best_bid"]]

        # 4. Standardization (OptionMetrics stores strikes multiplied by 1000)
        df["strike_price"] = df["strike_price"] / 1000.0
        df["mid_price"] = (df["best_bid"] + df["best_offer"]) / 2.0
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
