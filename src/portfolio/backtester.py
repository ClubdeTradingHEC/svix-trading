from typing import Dict, List

import numpy as np
import pandas as pd

from src.core.schemas import TradeSignal


class PortfolioSimulator:
    """Simulates a portfolio under capital constraints and market frictions."""

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        transaction_cost_bps: float = 5.0,
        annualization_factor: int = 252,
    ) -> None:
        """
        Args:
            initial_capital: Starting equity in base currency.
            transaction_cost_bps: Commissions + slippage per trade, in basis points.
            annualization_factor: Trading days per year.
        """
        self.initial_capital = initial_capital
        self.t_cost_rate = transaction_cost_bps / 10_000.0
        self.ann_factor = annualization_factor

    def _calculate_transaction_costs(
        self,
        current_weight: float,
        target_weight: float,
        portfolio_value: float,
    ) -> float:
        """
        Args:
            current_weight: Portfolio weight before the signal.
            target_weight: Desired weight from the signal.
            portfolio_value: Total equity at execution.

        Returns:
            Absolute transaction cost deducted from cash.
        """
        delta = abs(target_weight - current_weight)
        return delta * portfolio_value * self.t_cost_rate

    def _compute_risk_metrics(
        self,
        equity_curve: pd.Series,
        risk_free: float = 0.0,
    ) -> Dict[str, float]:
        """
        Args:
            equity_curve: Daily total equity, starting with the initial capital.
            risk_free: Average annual risk-free rate, used for excess returns.

        Returns:
            Sharpe, Sortino, Calmar and Max_Drawdown.
        """
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
        """
        Chronological event loop that updates cash, position and equity.

        Args:
            signals: Alpha signals, sorted by date.

        Returns:
            Daily ledger with Date, Position_Weight, Cash, Asset_Value,
            Total_Equity and Daily_Return.
        """
        signals = sorted(signals, key=lambda s: s.date)
        dt = 1 / self.ann_factor

        cash = self.initial_capital
        shares = 0.0
        prev_equity = self.initial_capital
        ledger = []

        for s in signals:
            price = s.execution_price
            if price is None or np.isnan(price) or price <= 0:
                raise ValueError(f"Invalid execution price on {s.date}: {price}")

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
                "Date": s.date,
                "Position_Weight": position_weight,
                "Cash": cash,
                "Asset_Value": asset_value,
                "Total_Equity": equity,
                "Daily_Return": equity / prev_equity - 1,
            }
            ledger.append(row)
            prev_equity = equity

            if equity <= 0:
                print(f"Ruin reached on {s.date}. Simulation stopped.")
                break

        df = pd.DataFrame(ledger).set_index("Date")

        equity_series = df["Total_Equity"].reset_index(drop=True)
        start = pd.Series([self.initial_capital])
        equity_curve = pd.concat([start, equity_series], ignore_index=True)

        rates = [s.risk_free_rate for s in signals]
        avg_rf = float(np.mean(rates)) if rates else 0.0

        metrics = self._compute_risk_metrics(equity_curve, avg_rf)
        for k, v in metrics.items():
            print(f"{k:>13}: {v:.4f}")

        return df
