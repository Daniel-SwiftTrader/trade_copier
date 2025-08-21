# scripts/manual_smoke_trade.py
from datetime import datetime
from trade_logic.engine import TradingEngine
from data_access.data_access import TerminalClient
from config import CONFIG

# ---- Pick your symbol and the fake Manager net to drive a delta ----
# target_position = -net_volume * trade_size_multiplier
# With net_volume=2.0 and multiplier=0.05 -> target = -0.10 -> SELL 0.10 if current position is 0
TEST_SYMBOL = "EURUSD"
FAKE_NET_LOTS = 2.0  # tweak this to drive a different delta

def fake_manager_rows():
    return [{
        "symbol": TEST_SYMBOL,
        "net_volume": FAKE_NET_LOTS,
        "positions": 5,
        "buy_volume": 3.0,
        "sell_volume": 1.0,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }]

def main():
    term = TerminalClient()
    if not term.init_and_login():
        print("Login failed. Check config/config.py credentials and server.")
        return

    engine = TradingEngine(fake_manager_rows, term)
    out = engine.cycle()

    print("----- RESULT -----")
    print("Trades executed:", out.get("trades_executed"))
    for r in out.get("usd_rows", []):
        if r.get("Symbol") == TEST_SYMBOL:
            print("Row:", r)

    term.shutdown()

if __name__ == "__main__":
    main()
