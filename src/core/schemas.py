"""
Core Data Contracts.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class OptionType(str, Enum):
    """Enumeration for option types."""

    CALL = "C"
    PUT = "P"


@dataclass(frozen=True)
class OptionChain:
    """
    Immutable volatility surface for a single maturity.
    Note: Analytics pipeline may require List[OptionChain] for constant maturity interpolation.
    """

    date: datetime
    maturity_days: float
    underlying_price: float
    risk_free_rate: float
    forward_price: float
    options_data: pd.DataFrame
    dividend_yield: float = 0.0

    def __post_init__(self) -> None:
        if self.maturity_days <= 0:
            raise ValueError(f"Invalid maturity: {self.maturity_days} days.")
        if self.options_data.empty:
            raise ValueError("Empty options data payload.")

        required = {"strike", "option_type", "bid", "ask", "mid_price"}
        if missing := required - set(self.options_data.columns):
            raise ValueError(f"Missing columns: {missing}.")

        if self.options_data[["strike", "mid_price"]].isnull().any().any():
            raise ValueError("NaN values detected in critical pricing columns.")


@dataclass(frozen=True)
class VolatilityMetrics:
    """
    Numerical integration results.
    Propagates underlying state (price, rates, dividends) required by Portfolio constraints.
    """

    date: datetime
    maturity_days: float
    is_interpolated: bool  # True if derived from two OptionChains (e.g., 30-day constant)
    underlying_price: float
    risk_free_rate: float  # Required downstream for portfolio Sharpe and funding costs
    dividend_yield: float  # Required downstream for Total Return calculations
    svix_annualized: float
    vix_annualized: float
    min_strike_used: float
    max_strike_used: float
    integration_points: int

    def __post_init__(self) -> None:
        if self.svix_annualized < 0 or self.vix_annualized < 0:
            raise ValueError("Calculated volatility cannot be negative.")
        if self.integration_points < 5:
            raise ValueError("Insufficient integration grid density.")

    @property
    def variance_premium(self) -> float:
        """Difference between log-return variance and simple-return variance."""
        return (self.vix_annualized**2) - (self.svix_annualized**2)


@dataclass(frozen=True)
class TradeSignal:
    """
    Target allocation vector for Delta-One S&P 500 trading.
    Strictly separates signal generation timestamp from execution
    timestamp to prevent look-ahead bias.
    """

    signal_date: datetime  # e.g., t (Market Close)
    target_execution_date: datetime  # e.g., t+1 (Market Open)
    underlying_price_at_signal: float
    target_weight: float
    risk_free_rate: float  # Propagated for margin/cash yield calculation
    dividend_yield: float  # Propagated for Total Return
    signal_confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if self.target_execution_date <= self.signal_date:
            raise ValueError("Execution date must be strictly after signal date (Look-ahead bias).")

        if np.isnan(self.target_weight) or np.isinf(self.target_weight):
            raise ValueError("Target weight must be a finite number.")

        if not -1.0 <= self.target_weight <= 1.0:
            raise ValueError(f"Target weight {self.target_weight} outside absolute bounds [-1, 1].")
