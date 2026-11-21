"""
Variance Premium Analytics Engine.
Implements the Carr-Madan model-free replication for VIX and Ian Martin's (2017) SVIX.
"""

from typing import List

import numpy as np
import pandas as pd
from scipy.integrate import simpson

from src.core.schemas import OptionChain, VolatilityMetrics


class VarianceCalculator:
    """
    Mathematical engine responsible for computing implied variance from option surfaces.
    Handles Out-of-the-Money (OTM) filtration, numerical integration, and constant-maturity interpolation.
    """

    @staticmethod
    def _isolate_otm_options(chain: OptionChain) -> pd.DataFrame:
        """
        Splits the volatility surface at the forward price.
        Retains strictly Out-of-the-Money (OTM) puts (K < F) and OTM calls (K >= F).

        Args:
            chain (OptionChain): The validated option chain contract.

        Returns:
            pd.DataFrame: A sorted continuum of OTM options mapped by strike.
        """
        options = chain.options_data
        forward = chain.forward_price

        otm_puts = options[(options["option_type"] == "P") & (options["strike"] < forward)]
        otm_calls = options[(options["option_type"] == "C") & (options["strike"] >= forward)]

        otm = pd.concat([otm_puts, otm_calls])
        return otm.sort_values("strike").reset_index(drop=True)

    @staticmethod
    def _integrate_variance(otm_surface: pd.DataFrame, chain: OptionChain, is_svix: bool) -> float:
        """
        Performs the numerical integration over the OTM surface.

        Mathematical distinction:
        - VIX: Weighting factor is proportional to 1 / K^2.
        - SVIX: Weighting factor is proportional to 1 / S_0^2 (Martin, 2017).

        Args:
            otm_surface (pd.DataFrame): The filtered OTM options from _isolate_otm_options.
            chain (OptionChain): The original chain (needed for S_0, r, T).
            is_svix (bool): Flag to toggle between the VIX and SVIX weighting schemes.

        Returns:
            float: The raw, annualized variance for this specific maturity.
        """
        strikes = otm_surface["strike"].to_numpy()
        prices = otm_surface["mid_price"].to_numpy()

        s0 = chain.underlying_price
        r = chain.risk_free_rate
        t = chain.maturity_days / 365

        if is_svix:
            integrand = prices
            factor = 2 / (t * np.exp(r * t) * s0**2)
        else:
            integrand = prices / strikes**2
            factor = 2 * np.exp(r * t) / t

        integral = simpson(integrand, x=strikes)
        return factor * integral

    @staticmethod
    def _interpolate_constant_maturity(
        var_t1: float, days_t1: float, var_t2: float, days_t2: float, target_days: int = 30
    ) -> float:
        """
        Applies time-weighted linear interpolation between two maturities to extract
        a constant maturity variance (standard CBOE methodology).

        Args:
            var_t1 (float): Annualized variance of the near-term expiration.
            days_t1 (float): Days to expiration for the near-term chain.
            var_t2 (float): Annualized variance of the next-term expiration.
            days_t2 (float): Days to expiration for the next-term chain.
            target_days (int): The target constant maturity.

        Returns:
            float: The interpolated, annualized constant maturity variance.
        """
        if days_t2 == days_t1:
            raise ValueError("days_t1 and days_t2 must differ to interpolate")
        w1 = (days_t2 - target_days) / (days_t2 - days_t1)
        w2 = (target_days - days_t1) / (days_t2 - days_t1)
        total_variance = days_t1 * var_t1 * w1 + days_t2 * var_t2 * w2
        return total_variance / target_days

    def compute_metrics(self, chains: List[OptionChain], target_days: int = 30) -> VolatilityMetrics:
        """
        Main orchestration method. Consumes the bracketing chains from the Data module
        and produces the final VolatilityMetrics contract.

        Args:
            chains (List[OptionChain]): Exactly two OptionChain objects (T1 < target and T2 >= target).
            target_days (int): The constant maturity target (default: 30).

        Returns:
            VolatilityMetrics: The validated numerical integration results.
        """
        if len(chains) != 2:
            raise ValueError(f"Analytics constraint: Expected exactly 2 chains for interpolation, received {len(chains)}.")

        # 1. Sort the two chains by maturity (near = T1, far = T2)
        near, far = sorted(chains, key=lambda chain: chain.maturity_days)

        # 2a. Keep only the OTM options of each chain
        otm_near = self._isolate_otm_options(near)
        otm_far = self._isolate_otm_options(far)

        # 2b. Variance of each chain, for the VIX and for the SVIX
        vix_near = self._integrate_variance(otm_near, near, is_svix=False)
        vix_far = self._integrate_variance(otm_far, far, is_svix=False)
        svix_near = self._integrate_variance(otm_near, near, is_svix=True)
        svix_far = self._integrate_variance(otm_far, far, is_svix=True)

        # 3. Bring both variances to the target maturity
        vix_var = self._interpolate_constant_maturity(vix_near, near.maturity_days, vix_far, far.maturity_days, target_days)
        svix_var = self._interpolate_constant_maturity(svix_near, near.maturity_days, svix_far, far.maturity_days, target_days)

        if vix_var < 0 or svix_var < 0:
            raise ValueError(f"Negative interpolated variance (VIX: {vix_var}, SVIX: {svix_var}).")

        # 2c. Strike range and grid density actually used
        all_strikes = pd.concat([otm_near["strike"], otm_far["strike"]])

        # 4-5. Macro state from the near chain, then the VolatilityMetrics contract (volatilities, not variances)
        return VolatilityMetrics(
            date=near.date,
            maturity_days=float(target_days),
            is_interpolated=True,
            underlying_price=near.underlying_price,
            risk_free_rate=near.risk_free_rate,
            dividend_yield=near.dividend_yield,
            svix_annualized=float(np.sqrt(svix_var)),
            vix_annualized=float(np.sqrt(vix_var)),
            min_strike_used=float(all_strikes.min()),
            max_strike_used=float(all_strikes.max()),
            integration_points=min(len(otm_near), len(otm_far)),
        )
