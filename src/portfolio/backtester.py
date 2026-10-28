import logging
from typing import Dict, List

import numpy as np
import pandas as pd

from src.core.schemas import TradeSignal

logger = logging.getLogger(__name__)


class PortfolioSimulator:
<<<<<<< HEAD
    """Simulates a portfolio under capital constraints and market frictions."""

=======
>>>>>>> 4b64741 (Format backtester and tests with ruff)
    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        transaction_cost_bps: float = 5.0,
        annualization_factor: int = 252,
    ) -> None:
<<<<<<< HEAD
        """
        Args:
            initial_capital: Starting equity in base currency.
            transaction_cost_bps: Commissions + slippage per trade, in basis points.
            annualization_factor: Trading days per year.
        """
=======
>>>>>>> 4b64741 (Format backtester and tests with ruff)

        self.initial_capital = initial_capital
        self.t_cost_rate = transaction_cost_bps / 10_000.0
        self.ann_factor = annualization_factor
        self.metrics: Dict[str, float] = {}

    def _calculate_transaction_costs(
        self,
        current_weight: float,
        target_weight: float,
        portfolio_value: float,
    ) -> float:
<<<<<<< HEAD
        """
        Args:
            current_weight: Portfolio weight before the signal.
            target_weight: Desired weight from the signal.
            portfolio_value: Total equity at execution.

        Returns:
            Absolute transaction cost deducted from cash.
        """
=======
>>>>>>> 4b64741 (Format backtester and tests with ruff)

        delta = abs(target_weight - current_weight)
        return delta * portfolio_value * self.t_cost_rate

    def _compute_risk_metrics(
        self,
        equity_curve: pd.Series,
        risk_free: float = 0.0,
    ) -> Dict[str, float]:
<<<<<<< HEAD
        """
        Args:
            equity_curve: Daily total equity, starting with the initial capital.
            risk_free: Average annual risk-free rate, used for excess returns.

        Returns:
            Sharpe, Sortino, Calmar and Max_Drawdown.
        """
=======
>>>>>>> 4b64741 (Format backtester and tests with ruff)

        nan = float("nan")
        if (equity_curve <= 0).any():
            return {"Sharpe": nan, "Sortino": nan, "Calmar": nan, "Max_Drawdown": -1.0}

        returns = equity_curve.pct_change().dropna()
        if len(returns) < 2 or returns.std() == 0:
            return {"Sharpe": nan, "Sortino": nan, "Calmar": nan, "Max_Drawdown": nan}

        excess = returns - risk_free / self.ann_factor
        max_dd = (equity_curve / equity_curve.cummax() - 1).min()

        sharpe = excess.mean() / excess.std() * np.sqrt(self.ann_factor)

        downside = np.sqrt((excess.clip(upper=0) ** 2).mean())
        sortino = np.nan
        if downside > 0:
            sortino = excess.mean() / downside * np.sqrt(self.ann_factor)

        years = len(returns) / self.ann_factor
        ann_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1 / years) - 1
        calmar = ann_return / abs(max_dd) if max_dd < 0 else nan

        return {"Sharpe": sharpe, "Sortino": sortino, "Calmar": calmar, "Max_Drawdown": max_dd}

    def run_simulation(self, signals: List[TradeSignal]) -> pd.DataFrame:
<<<<<<< HEAD
        """
        Chronological event loop that updates cash, position and equity.

        Metrics are stored in self.metrics so the caller can read them.

        Args:
            signals: Alpha signals.

        Returns:
            Daily ledger with Date, Position_Weight, Cash, Asset_Value,
            Total_Equity and Daily_Return.
        """
=======
>>>>>>> 4b64741 (Format backtester and tests with ruff)

        signals = sorted(signals, key=lambda s: s.target_execution_date)
        dt = 1 / self.ann_factor

        cash = self.initial_capital
        shares = 0.0
        prev_equity = self.initial_capital
        ledger = []

        for s in signals:
            price = s.underlying_price_at_signal
            if price is None or np.isnan(price) or price <= 0:
                raise ValueError(f"Invalid price on signal date {s.signal_date}: {price}")

            asset_value = shares * price

            cash += cash * s.risk_free_rate * dt
            cash += asset_value * s.dividend_yield * dt
            equity = cash + asset_value

            if equity > 0:
                current_weight = asset_value / equity
                cost = self._calculate_transaction_costs(current_weight, s.target_weight, equity)
                cash -= cost
                equity -= cost

                target_value = s.target_weight * equity
                cash -= target_value - asset_value
                shares = target_value / price
                asset_value = target_value

            position_weight = asset_value / equity if equity > 0 else 0.0
            row = {
                "Date": s.target_execution_date,
                "Position_Weight": position_weight,
                "Cash": cash,
                "Asset_Value": asset_value,
                "Total_Equity": equity,
                "Daily_Return": equity / prev_equity - 1,
            }
            ledger.append(row)
            prev_equity = equity

            if equity <= 0:
                logger.warning(
                    "Ruin state reached on %s. Terminating simulation.",
                    s.target_execution_date,
                )
                break

        df = pd.DataFrame(ledger).set_index("Date")

        equity_curve = pd.concat(
            [pd.Series([self.initial_capital]), df["Total_Equity"].reset_index(drop=True)],
            ignore_index=True,
        )

        avg_rf = float(np.mean([s.risk_free_rate for s in signals])) if signals else 0.0
        self.metrics = self._compute_risk_metrics(equity_curve, avg_rf)
        for name, value in self.metrics.items():
            logger.info("%s: %.4f", name, value)

        return df
