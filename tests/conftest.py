"""
Pytest fixtures & stubs:
- MT5 stub covering the subset used by data_access + engine
- Fake Manager API for ManagerClient.get_net_positions()
- Shared fixtures for clean CONFIG tweaks during tests
"""

import sys
import types
from types import SimpleNamespace
import math
import time
import random
import pytest


# ----------------- MT5 Stub -----------------

def _mt5_stub():
    mt5 = types.SimpleNamespace()
    # Trade constants
    mt5.TRADE_ACTION_DEAL = 1
    mt5.TRADE_ACTION_PENDING = 5
    mt5.ORDER_TYPE_BUY = 0
    mt5.ORDER_TYPE_SELL = 1
    mt5.ORDER_TYPE_BUY_LIMIT = 2
    mt5.ORDER_TYPE_SELL_LIMIT = 3
    mt5.ORDER_TIME_GTC = 2
    mt5.ORDER_FILLING_IOC = 1
    mt5.TRADE_RETCODE_DONE = 10009

    mt5.POSITION_TYPE_BUY = 0
    mt5.POSITION_TYPE_SELL = 1
    mt5.TIMEFRAME_M1 = 1

    # Simple state
    _connected = {"connected": False}
    _positions = []  # list of Position
    _orders = []
    _symbol_info = {}
    _ticks = {}
    _deals = []  # history deals

    class _TerminalInfo:
        def __init__(self, connected):
            self.connected = connected

    class _AccountInfo:
        def __init__(self, balance=100000.0, equity=100000.0, margin=0.0, margin_level=0.0, profit=0.0):
            self.balance = balance
            self.equity = equity
            self.margin = margin
            self.margin_level = margin_level
            self.profit = profit

    class _Position:
        def __init__(self, symbol, typ, volume, price=100.0, profit=0.0, ticket=None):
            self.symbol = symbol
            self.type = typ
            self.volume = float(volume)
            self.price_open = price
            self.price_current = price
            self.profit = float(profit)
            self.ticket = ticket if ticket is not None else random.randint(100000, 999999)

    class _OrderResult:
        def __init__(self, retcode, comment=""):
            self.retcode = retcode
            self.comment = comment

    class _Info:
        def __init__(self, volume_min=0.01, volume_step=0.01, digits=2, point=0.01):
            self.volume_min = volume_min
            self.volume_step = volume_step
            self.digits = digits
            self.point = point

    class _Tick:
        def __init__(self, bid=100.0, ask=100.02):
            self.bid = bid
            self.ask = ask

    def initialize():
        _connected["connected"] = True
        return True

    def login(*args, **kwargs):
        return True

    def terminal_info():
        return _TerminalInfo(_connected["connected"])

    def shutdown():
        _connected["connected"] = False
        return True

    def positions_get(symbol=None):
        if symbol is None:
            return list(_positions)
        return [p for p in _positions if p.symbol == symbol]

    def orders_get():
        return list(_orders)

    def order_send(req: dict):
        # Market DEALs fill instantly; PENDING ignored for simplicity
        if req.get("action") == mt5.TRADE_ACTION_DEAL:
            side_buy = req.get("type") == mt5.ORDER_TYPE_BUY
            sym = req["symbol"]
            vol = float(req["volume"])

            # If a position ticket is provided, treat this as a CLOSE request
            pos_ticket = req.get("position")
            if pos_ticket is not None:
                # Find the matching open position and remove (close) it
                for i, p in enumerate(list(_positions)):
                    if p.ticket == pos_ticket and p.symbol == sym:
                        # naive close: remove position; ignore partial close edge-cases
                        _positions.pop(i)
                        break
                return _OrderResult(mt5.TRADE_RETCODE_DONE, "closed")
            else:
                # OPEN a new position (very naive netting model)
                if side_buy:
                    _positions.append(_Position(sym, mt5.POSITION_TYPE_BUY, vol, ticket=random.randint(100000, 999999)))
                else:
                    _positions.append(_Position(sym, mt5.POSITION_TYPE_SELL, vol, ticket=random.randint(100000, 999999)))
                return _OrderResult(mt5.TRADE_RETCODE_DONE, "opened")

        # Non-DEAL requests considered not filled in this stub
        return _OrderResult(0, "pending not filled")


    def symbol_info(symbol):
        return _symbol_info.get(symbol, _Info())

    def symbol_info_tick(symbol):
        return _ticks.get(symbol, _Tick())

    def symbol_select(symbol, select=True):
        return True

    def copy_rates_from_pos(symbol, timeframe, start_pos, count):
        # Return a single bar with 'close' price
        return [{"close": 100.0}]

    def account_info():
        # Sum PnL from positions as unrealized
        total_pnl = sum(p.profit for p in _positions)
        return _AccountInfo(balance=100000.0, equity=100000.0 + total_pnl, margin=0.0, margin_level=0.0, profit=total_pnl)

    def history_deals_get(time_from, time_to):
        return [SimpleNamespace(profit=d) for d in _deals]

    # Expose internals so tests can arrange state
    mt5._positions = _positions
    mt5._orders = _orders
    mt5._ticks = _ticks
    mt5._symbol_info = _symbol_info
    mt5._deals = _deals
    mt5._Position = _Position
    mt5._Info = _Info
    mt5._Tick = _Tick
    mt5._AccountInfo = _AccountInfo

    # Bind functions
    mt5.initialize = initialize
    mt5.login = login
    mt5.terminal_info = terminal_info
    mt5.shutdown = shutdown
    mt5.positions_get = positions_get
    mt5.orders_get = orders_get
    mt5.order_send = order_send
    mt5.symbol_info = symbol_info
    mt5.symbol_info_tick = symbol_info_tick
    mt5.symbol_select = symbol_select
    mt5.copy_rates_from_pos = copy_rates_from_pos
    mt5.account_info = account_info
    mt5.history_deals_get = history_deals_get

    return mt5


@pytest.fixture(scope="session", autouse=True)
def patch_mt5_in_sys_modules():
    """
    Ensure imports of `MetaTrader5` across the project resolve to our stub.
    Import test-target modules AFTER this fixture is in effect.
    """
    mt5 = _mt5_stub()
    sys.modules["MetaTrader5"] = mt5
    return mt5


# ----------------- Fake Manager API -----------------

class FakeSummary:
    def __init__(self, volume_net, buy_clients, sell_clients, positions):
        # Note: VolumeNet already in lots (rc4 semantics)
        self.VolumeNet = volume_net
        self.VolumeBuyClients = buy_clients   # raw units (need /10000)
        self.VolumeSellClients = sell_clients # raw units (need /10000)
        self.PositionClients = positions


class FakeManagerAPI:
    def __init__(self, table):
        """
        table: dict[symbol] -> FakeSummary
        """
        self._table = table

    def SummaryTotal(self):
        return len(self._table)

    def SummaryGet(self, symbol):
        return self._table.get(symbol, False)


# ----------------- Quick helpers -----------------

@pytest.fixture
def fake_manager_table():
    # Example with XAUUSD and EURUSD
    return {
        "XAUUSD": FakeSummary(volume_net=4.50, buy_clients=230000, sell_clients=80000, positions=12),
        "EURUSD": FakeSummary(volume_net=-3.20, buy_clients=100000, sell_clients=420000, positions=20),
    }


@pytest.fixture
def reset_config():
    # Provide a copy of CONFIG the tests can safely mutate
    from config import CONFIG
    orig = {k: (v.copy() if isinstance(v, dict) else v) for k, v in CONFIG.items()}
    yield CONFIG
    # restore
    for k in list(CONFIG.keys()):
        if isinstance(CONFIG[k], dict):
            CONFIG[k].clear()
            CONFIG[k].update(orig[k])
        else:
            CONFIG[k] = orig[k]


@pytest.fixture
def stub_trend_allow(monkeypatch):
    # Always allow trades; trend=up
    from types import SimpleNamespace
    def _fake_compute_trend_metrics(symbol):
        return SimpleNamespace(trend="up", sma_diff=0.001, rsi=55.0, macd=0.2)
    monkeypatch.setattr("indicators.indicators.compute_trend_metrics", _fake_compute_trend_metrics)
