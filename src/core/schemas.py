from dataclasses import dataclass
from datetime import datetime
import pandas as pd


@dataclass
class OptionChain:
    """
    Contrat de données pour le poste Data (Nizar).
    Représente la surface de volatilité filtrée pour une maturité donnée.
    """

    date: datetime
    maturity_days: float
    underlying_price: float
    risk_free_rate: float
    forward_price: float

    # Le DataFrame doit contenir les colonnes :
    # ['strike', 'option_type', 'bid', 'ask', 'mid_price']
    options_data: pd.DataFrame


@dataclass
class VolatilityMetrics:
    """
    Contrat de données pour le poste Analytics (Nelson).
    Représente les résultats de l'intégration numérique.
    """

    date: datetime
    svix_annualized: float
    vix_annualized: float

    @property
    def variance_premium(self) -> float:
        """Différence entre la variance log (VIX) et simple (SVIX)"""
        return (self.vix_annualized**2) - (self.svix_annualized**2)


@dataclass
class TradeSignal:
    """
    Contrat de données pour le poste Signals (Adam) et Portfolio (Justine).
    Représente la pondération cible envoyée au backtester.
    """

    date: datetime
    target_weight: float  # Compris entre -1.0 (Short maximal) et 1.0 (Long maximal)
    signal_confidence: float  # Optionnel: Z-score ou conviction du modèle
