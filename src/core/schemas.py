"""
Core Data Contracts.
Enforces type safety, data integrity, and strict boundaries across research modules.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class OptionType(str, Enum):
    """Enumeration for option types to prevent arbitrary string instantiation."""
    CALL = 'C'
    PUT = 'P'


@dataclass(frozen=True)
class OptionChain:
    """
    Immutable data contract mapping the filtered volatility surface for a given maturity.
    Expected upstream source: WRDS Data Engineering pipeline.
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
            raise ValueError("Data pipeline breach: options_data DataFrame is empty.")

        required_columns = {'strike', 'option_type', 'bid', 'ask', 'mid_price'}
        missing = required_columns - set(self.options_data.columns)
        if missing:
            raise ValueError(f"Data pipeline breach: missing required columns {missing}.")

        if self.options_data[['strike', 'mid_price']].isnull().any().any():
            raise ValueError("Data pipeline breach: NaN values detected in strikes or prices.")


@dataclass(frozen=True)
class VolatilityMetrics:
    """
    Immutable data contract representing numerical integration results.
    Expected upstream source: Analytics pipeline (Carr-Madan framework).
    """
    date: datetime
    maturity_days: float
    svix_annualized: float
    vix_annualized: float
    min_strike_used: float
    max_strike_used: float
    integration_points: int

    def __post_init__(self) -> None:
        if self.svix_annualized < 0 or self.vix_annualized < 0:
            raise ValueError("Analytics pipeline breach: Calculated volatility is negative.")
            
        if self.integration_points < 5:
            raise ValueError(
                "Analytics pipeline breach: Insufficient strike density for numerical integration."
            )

    @property
    def variance_premium(self) -> float:
        """
        Computes the theoretical variance premium.
        Defined as the difference between log-return variance and simple-return variance.
        """
        return (self.vix_annualized ** 2) - (self.svix_annualized ** 2)


@dataclass(frozen=True)
class TradeSignal:
    """
    Immutable data contract representing the target allocation vector.
    Expected upstream source: Alpha Signals pipeline.
    """
    date: datetime
    target_weight: float
    signal_confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if np.isnan(self.target_weight) or np.isinf(self.target_weight):
            raise ValueError("Signal pipeline breach: target_weight is NaN or Infinite.")

        if not -1.0 <= self.target_weight <= 1.0:
            raise ValueError(
                f"Signal pipeline breach: target_weight {self.target_weight} exceeds bounds [-1, 1]."
            )