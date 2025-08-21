from types import SimpleNamespace
import pandas as pd
import os

def _fake_manager_rows():
    # ManagerClient.get_net_positions() shape
    return [
        {"symbol": "XAUUSD", "net_volume": 4.0, "positions": 10, "buy_volume": 20.0, "sell_volume": 16.0, "timestamp": "t"},
        {"symbol": "EURUSD", "net_volume": -2.0, "positions": 5, "buy_volume": 5.0, "sell_volume": 7.0, "timestamp": "t"},
    ]


def test_engine_cycle_executes_when_allowed(monkeypatch, patch_mt5_in_sys_modules, reset_config):
    import MetaTrader5 as mt5
    from trade_logic.engine import TradingEngine
    from data_access.data_access import TerminalClient
    from config import CONFIG

    # trend always allows
    def _allow(_symbol):
        return SimpleNamespace(trend="up", sma_diff=0.002, rsi=55.0, macd=0.1)
    monkeypatch.setattr("indicators.indicators.compute_trend_metrics", _allow)

    # prices/ticks & symbol info
    mt5._ticks["XAUUSD"] = mt5._Tick(bid=2400.00, ask=2400.20)
    mt5._ticks["EURUSD"] = mt5._Tick(bid=1.1000, ask=1.1002)
    mt5._symbol_info["XAUUSD"] = mt5._Info(volume_min=0.10, volume_step=0.10, digits=2, point=0.01)
    mt5._symbol_info["EURUSD"] = mt5._Info(volume_min=0.01, volume_step=0.01, digits=5, point=0.00001)

    # no existing positions
    mt5._positions.clear()

    # ensure we don't trip risk guard
    mt5._deals.clear()  # realized pnl = 0
    CONFIG["risk_management"]["daily_loss_limit"] = -1000.0
    CONFIG["trade_management"]["trade_size_multiplier"] = 0.05
    CONFIG["trade_management"]["max_position_size"] = 300.0

    engine = TradingEngine(_fake_manager_rows, TerminalClient())
    out = engine.cycle()

    assert "usd_rows" in out and "pair_rows" in out
    # We should have attempted trades; stub fills market DEAls
    assert out["trades_executed"] >= 1
    # GUI row shape includes PNL column
    assert set(out["usd_rows"][0].keys()) >= {"Symbol", "Trade Delta", "PNL"}


def test_engine_blocks_on_daily_loss_and_auto_close(monkeypatch, patch_mt5_in_sys_modules, reset_config):
    import MetaTrader5 as mt5
    from trade_logic.engine import TradingEngine
    from data_access.data_access import TerminalClient
    from config import CONFIG

    # trend always allows
    monkeypatch.setattr("indicators.indicators.compute_trend_metrics",
                        lambda s: SimpleNamespace(trend="up", sma_diff=0.002, rsi=55.0, macd=0.1))

    # Put a position so we can verify auto-close
    mt5._positions.clear()
    mt5._positions.append(mt5._Position("XAUUSD", mt5.POSITION_TYPE_BUY, 1.0))

    # Force realized PnL to be under the limit (breach)
    mt5._deals[:] = [-6000.0]  # realized today
    CONFIG["risk_management"]["daily_loss_limit"] = -5000.0
    CONFIG["risk_management"]["auto_close_on_daily_loss_limit"] = True

    engine = TradingEngine(_fake_manager_rows, TerminalClient())
    res = engine.cycle()
    # No trades executed
    assert res.get("trades_executed", 0) == 0
    # Auto-close should have cleared positions
    assert len(mt5._positions) == 0
