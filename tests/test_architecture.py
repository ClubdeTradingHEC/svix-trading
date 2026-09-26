import importlib
from datetime import datetime

from src.core.schemas import TradeSignal


def test_imports():
    """Vérifie que tous les modules sont détectés par Python."""
    modules = [
        "src.core",
        "src.data",
        "src.analytics",
        "src.signals",
        "src.portfolio",
    ]
    for mod in modules:
        assert importlib.import_module(mod) is not None


def test_schemas_loading():
    """Vérifie que les dataclasses sont correctement formatées."""
    signal = TradeSignal(date=datetime(2026, 9, 25), target_weight=0.5, signal_confidence=1.2)
    assert signal.target_weight == 0.5
