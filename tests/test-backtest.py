# tests/test_backtester.py
import logging
import math
from types import SimpleNamespace

import pandas as pd
import pytest

from src.portfolio.backtester import PortfolioSimulator


def make_signal(date, weight=0.0, price=100.0, rf=0.0, div=0.0):
    return SimpleNamespace(
        signal_date=date,
        target_execution_date=date,
        underlying_price_at_signal=price,
        target_weight=weight,
        risk_free_rate=rf,
        dividend_yield=div,
    )


D1 = pd.Timestamp("2026-01-02")
D2 = pd.Timestamp("2026-01-05")
D3 = pd.Timestamp("2026-01-06")


def test_no_position_keeps_capital():
    sim = PortfolioSimulator(initial_capital=1_000_000)
    ledger = sim.run_simulation([make_signal(D1), make_signal(D2)])

    assert ledger["Total_Equity"].iloc[-1] == pytest.approx(1_000_000)


def test_cash_accrues_risk_free_interest():
    # 25.2% annual rate, dt = 1/252 -> 0.1% daily growth on 1M
    sim = PortfolioSimulator(initial_capital=1_000_000)
    ledger = sim.run_simulation([make_signal(D1, rf=0.252)])

    assert ledger["Total_Equity"].iloc[0] == pytest.approx(1_001_000)


def test_rebalance_applies_transaction_cost():
    # 5 bps on 0.5 * 1M = 250 cost; equity after cost = 999_750
    sim = PortfolioSimulator(initial_capital=1_000_000, transaction_cost_bps=5)
    ledger = sim.run_simulation([make_signal(D1, weight=0.5, price=100)])
    row = ledger.iloc[0]

    assert row["Total_Equity"] == pytest.approx(999_750)
    assert row["Asset_Value"] == pytest.approx(499_875)
    assert row["Cash"] == pytest.approx(499_875)
    assert row["Position_Weight"] == pytest.approx(0.5)


def test_signals_processed_in_execution_date_order():
    sim = PortfolioSimulator()
    ledger = sim.run_simulation([make_signal(D3), make_signal(D1), make_signal(D2)])

    assert list(ledger.index) == [D1, D2, D3]


def test_ruin_stops_simulation_and_logs(caplog):
    # Leverage 2x on day 1, then a 50% drop wipes out equity on day 2
    sim = PortfolioSimulator(initial_capital=1_000_000, transaction_cost_bps=5)
    signals = [make_signal(D1, weight=2.0, price=100), make_signal(D2, weight=2.0, price=50)]

    with caplog.at_level(logging.WARNING):
        ledger = sim.run_simulation(signals)

    assert len(ledger) == 2
    assert ledger["Total_Equity"].iloc[-1] <= 0
    assert "Ruin state reached" in caplog.text
    assert sim.metrics["Max_Drawdown"] == -1.0


def test_invalid_price_raises():
    sim = PortfolioSimulator()
    with pytest.raises(ValueError):
        sim.run_simulation([make_signal(D1, price=0.0)])
    with pytest.raises(ValueError):
        sim.run_simulation([make_signal(D1, price=float("nan"))])


def test_max_drawdown_on_known_curve():
    sim = PortfolioSimulator()
    curve = pd.Series([100.0, 120.0, 60.0, 90.0])
    metrics = sim._compute_risk_metrics(curve)

    assert metrics["Max_Drawdown"] == pytest.approx(-0.5)


def test_sharpe_is_nan_for_flat_curve():
    sim = PortfolioSimulator()
    metrics = sim._compute_risk_metrics(pd.Series([100.0, 100.0, 100.0]))

    assert math.isnan(metrics["Sharpe"])


def test_metrics_stored_on_instance():
    sim = PortfolioSimulator()
    sim.run_simulation([make_signal(D1, weight=0.5), make_signal(D2, weight=0.5)])

    assert set(sim.metrics) == {"Sharpe", "Sortino", "Calmar", "Max_Drawdown"}