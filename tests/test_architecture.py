def test_imports():
    """Vérifie que tous les modules sont détectés par Python."""
    import src.data
    import src.analytics
    import src.signals
    import src.portfolio

    assert True


def test_schemas_loading():
    """Vérifie que les dataclasses sont correctement formatées."""
    from src.core.schemas import TradeSignal
    from datetime import datetime

    signal = TradeSignal(date=datetime(2026, 9, 25), target_weight=0.5, signal_confidence=1.2)
    assert signal.target_weight == 0.5
