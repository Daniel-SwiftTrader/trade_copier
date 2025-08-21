import pytest

@pytest.mark.skipif("tkinter" not in globals(), reason="tkinter not available in environment")
def test_gui_smoke(monkeypatch):
    import tkinter as tk
    from gui.gui import TradingGUI

    root = tk.Tk()
    root.withdraw()
    app = TradingGUI(root)

    payload = {
        "usd_rows": [
            {"Symbol": "XAUUSD", "Net USD Position": "4.00", "Trade Position": "0.00",
             "Target Position": "-0.20", "Trade Delta": "-0.20", "Trend": "Up",
             "Trend Strength": 0.001, "RSI": 55.0, "MACD": 0.1, "Reason": "Test", "PNL": 0.0}
        ],
        "pair_rows": [
            {"Symbol": "XAUUSD", "Trades": 10, "Long": 23.0, "Short": 8.0, "Net Position": 4.0}
        ],
        "trades_executed": 1
    }
    app.update_from_engine(payload)

    # If it didn't explode, basic rendering is fine
    # Check at least one item inserted
    assert len(app.usd_tree.get_children()) == 1
    assert len(app.pair_tree.get_children()) == 1

    root.destroy()
