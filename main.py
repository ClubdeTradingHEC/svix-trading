from datetime import datetime
import logging

from src.data.wrds_loader import WRDSOptionLoader
from src.analytics.variance_calculator import VariancePremiumCalculator
from src.signals.signal_generator import AlphaSignalGenerator
from src.portfolio.backtester import PortfolioSimulator

# Configure basic logging for the terminal
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def run_pipeline():
    logging.info("Starting SVIX Quantitative Pipeline...")
    target_date = datetime(2026, 9, 25)

    # 1. DATA PIPELINE (Nizar)
    logging.info("--- Step 1: Data Extraction ---")
    data_loader = WRDSOptionLoader()
    try:
        chains = data_loader.get_interpolation_chains(date=target_date, target_days=30)
        logging.info("Data extracted successfully.")
    except NotImplementedError as e:
        logging.warning(f"Data Module pending: {e}")
        chains = [] # Placeholder to allow script to continue

    # 2. ANALYTICS PIPELINE (Nelson)
    logging.info("--- Step 2: Analytics & Variance ---")
    calculator = VariancePremiumCalculator()
    try:
        metrics = calculator.compute_metrics(chains=chains)
        logging.info("Variance computed successfully.")
    except NotImplementedError as e:
        logging.warning(f"Analytics Module pending: {e}")
        metrics = None

    # 3. SIGNALS PIPELINE (Adam)
    logging.info("--- Step 3: Alpha Signal Generation ---")
    signal_generator = AlphaSignalGenerator()
    try:
        # Adam expects a list of historical metrics
        signals = signal_generator.generate_signals(metrics_history=[metrics] if metrics else [])
        logging.info("Signals generated successfully.")
    except NotImplementedError as e:
        logging.warning(f"Signals Module pending: {e}")
        signals = []

    # 4. PORTFOLIO PIPELINE (Justine)
    logging.info("--- Step 4: Portfolio Simulation ---")
    backtester = PortfolioSimulator(initial_capital=1_000_000.0)
    try:
        equity_curve = backtester.run_simulation(signals=signals)
        logging.info("Backtest completed successfully.")
    except NotImplementedError as e:
        logging.warning(f"Portfolio Module pending: {e}")


if __name__ == "__main__":
    run_pipeline()