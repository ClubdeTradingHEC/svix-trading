# SVIX Arbitrage & Quantitative Trading Engine

A quantitative research framework for volatility arbitrage and equity risk premium estimation based on **Ian Martin's (2017) Simple Variance Index (SVIX)**.

Developed by the **Drift & Diffusion Team** — **HEC Trading Club**.

---

## Overview

Unlike the CBOE VIX, which measures the risk-neutral expected variance of **log returns**, **SVIX** estimates the variance of **simple returns**, providing a model-free lower bound on the expected market excess return.

$$
\mathbb{E}^{\mathbb{P}}[R_m] - R_f \geq \frac{1}{2}SVIX_T^2
$$

The project includes:

- Option surface ingestion and cleaning (WRDS / OptionMetrics)
- Model-free SVIX computation via Carr–Madan replication
- Volatility dispersion and equity risk premium signal generation
- Systematic backtesting with realistic execution and risk management

The implemented replication formula is:

$$
SVIX_T^2 =
\frac{2e^{rT}}{TS_0^2}
\left[
\int_0^{F_T} P(K)\,dK
+
\int_{F_T}^{\infty} C(K)\,dK
\right]
$$

---

## Repository Structure

```text
src/
├── core/          # Shared data models and schemas
├── data/          # WRDS connector and option chain processing
├── analytics/     # SVIX replication, quadrature, Black–Scholes
├── signals/       # Alpha research and risk premium signals
└── portfolio/     # Backtesting, execution and risk overlay
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/ClubdeTradingHEC/svix-trading.git
cd svix-trading
```

Create the virtual environment and install dependencies with **uv**:

```bash
uv venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
uv sync
```

Configure your WRDS credentials in a `.env` file:

```env
WRDS_USERNAME=your_wrds_username
```

---

## Usage

### Compute SVIX

```python
from src.analytics.svix import SVIXCalculator
from src.analytics.black_scholes import generate_mock_chain

chain = generate_mock_chain(s0=5000.0, rate=0.04, maturity=30 / 365)

svix = SVIXCalculator().compute_svix(chain)
print(f"Annualized SVIX: {svix:.4f}")
```

### Run a Backtest

```python
from src.signals.risk_bound import BoundSignalGenerator
from src.portfolio.backtester import BacktestEngine

signals = BoundSignalGenerator().generate(svix_series, spx_returns)

engine = BacktestEngine(initial_capital=1_000_000, fee_bps=5.0)

results = engine.run(signals)
print(results.summary())
```

### Run Tests

```bash
uv run pytest tests -v
```

---

## Development

Feature branches follow the convention:

```text
feat/data-pipeline
feat/analytics-svix
feat/signal-research
feat/backtest-engine
```

All pull requests must pass the complete test suite before review.

---

## References

- Martin, I. (2017). *What Is the Expected Return on the Market?* Quarterly Journal of Economics, 132(1), 367–433.
- Carr, P., & Madan, D. (1998). *Towards a Theory of Volatility Trading.*
- Breeden, D. T., & Litzenberger, R. H. (1978). *Prices of State-Contingent Claims Implicit in Option Prices.*

---

## Authors


**Léandre Iskin** — Head of Research & Strategy Formulation

**Nelson Gillespie** — Senior Quantitative Analyst, Analytics

**Adam Burman** — Senior Quantitative Analyst, Alpha Signals

**Nizar Kazimi** — Quantitative Analyst, Data Engineering

**Justine Gonthier** — Quantitative Analyst, Portfolio & Risk Management
