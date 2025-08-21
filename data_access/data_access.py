"""
Data-access layer for MT5 Manager (exposures) and MT5 Terminal (trading).
"""

from datetime import datetime
import time
import threading
import queue
import MetaTrader5 as mt5

from config import SYMBOL_CONFIG
from config import CONFIG


class ManagerClient:
    """Wraps MT5 Manager summary calls to get client net positions per symbol (in lots)."""

    def __init__(self, manager_api_cls=None):
        # Lazily import to avoid hard dependency at import-time if SDK not present
        self._manager_api_cls = manager_api_cls

    def get_net_positions(self, manager_api):
        """
        Returns a list[dict] with keys:
          symbol, net_volume, positions, buy_volume, sell_volume, timestamp
        """
        exposure_rows = []
        total = manager_api.SummaryTotal()
        if total <= 0:
            return exposure_rows

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for symbol in SYMBOL_CONFIG["symbols"]:
            s = manager_api.SummaryGet(symbol)
            if s is False:
                continue

            # IMPORTANT: DO NOT DIVIDE VolumeNet (already in lots in your environment)
            net_lots = round(getattr(s, "VolumeNet", 0.0), 2)

            # Keep rc4 behavior: divide client buy/sell by 10000
            buy_raw = getattr(s, "VolumeBuyClients", 0)
            sell_raw = getattr(s, "VolumeSellClients", 0)
            buy_lots = round(buy_raw / 10000.0, 2) if buy_raw > 0 else 0.0
            sell_lots = round(sell_raw / 10000.0, 2) if sell_raw > 0 else 0.0
            positions = getattr(s, "PositionClients", 0)

            exposure_rows.append({
                "symbol": symbol,
                "net_volume": net_lots,
                "positions": positions,
                "buy_volume": buy_lots,
                "sell_volume": sell_lots,
                "timestamp": now
            })
        return exposure_rows


class TerminalClient:
    """Thin wrapper over MetaTrader5 terminal functions used by the engine."""

    def init_and_login(self) -> bool:
        if not mt5.initialize():
            return False
        return mt5.login(
            int(CONFIG["connection"]["terminal_login"]),
            password=CONFIG["connection"]["terminal_password"],
            server=CONFIG["connection"]["terminal_server"]
        )

    def shutdown(self):
        if mt5.terminal_info() and mt5.terminal_info().connected:
            mt5.shutdown()

    def get_current_position(self, symbol: str) -> float:
        term_symbol = SYMBOL_CONFIG["symbol_mapping"].get(symbol, symbol)
        positions = mt5.positions_get(symbol=term_symbol)
        if not positions:
            return 0.0
        net = sum(p.volume if p.type == mt5.POSITION_TYPE_BUY else -p.volume for p in positions)
        return round(net, 2)

    def get_mid_price(self, symbol: str):
        term_symbol = SYMBOL_CONFIG["symbol_mapping"].get(symbol, symbol)
        tick = mt5.symbol_info_tick(term_symbol)
        if tick is None:
            rates = mt5.copy_rates_from_pos(term_symbol, mt5.TIMEFRAME_M1, 0, 1)
            return rates[0]['close'] if rates is not None and len(rates) > 0 else None
        return (tick.bid + tick.ask) / 2

    def positions_get(self):
        return mt5.positions_get()

    def orders_get(self):
        return mt5.orders_get()

    def order_send(self, request):
        return mt5.order_send(request)

    def symbol_info(self, symbol):
        return mt5.symbol_info(symbol)

    def symbol_info_tick(self, symbol):
        return mt5.symbol_info_tick(symbol)

    def select_symbol(self, symbol, select=True):
        return mt5.symbol_select(symbol, select)
