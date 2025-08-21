"""
Symbol configuration for trading/execution and exposure calculations.

Notes
-----
- This file intentionally contains *no ATR* references.
- `symbol_mapping` lets you map Manager symbols (exposure source) to
  Terminal symbols (execution). If your broker uses identical names,
  keep the mapping 1:1.
- `currency_to_usd_pair` is used to translate non-USD exposures into a
  USD pair for conversion (e.g., CHF → USDCHF).
"""

SYMBOL_CONFIG = {
    # Symbols we monitor/trade. Feel free to extend.
    "symbols": [
        # Majors
        "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF", "AUDUSD", "NZDUSD",
        # JPY crosses
        "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY",
        # Common crosses
        "EURAUD", "EURGBP", "EURNZD", "AUDNZD", "GBPAUD", "GBPCAD", "GBPNZD",
        "AUDCHF", "CADCHF", "EURCHF", "GBPCHF", "NZDCHF",
        # Metals & Crypto
        "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "SOLUSD",
    ],

    # Manager → Terminal symbol mapping (1:1 by default)
    "symbol_mapping": {
        "EURUSD": "EURUSD.ecn",
        "GBPUSD": "GBPUSD.ecn",
        "USDJPY": "USDJPY.ecn",
        "USDCAD": "USDCAD.ecn",
        "USDCHF": "USDCHF.ecn",
        "AUDUSD": "AUDUSD.ecn",
        "NZDUSD": "NZDUSD.ecn",
        "EURJPY": "EURJPY.ecn",
        "GBPJPY": "GBPJPY.ecn",
        "AUDJPY": "AUDJPY.ecn",
        "CADJPY": "CADJPY.ecn",
        "NZDJPY": "NZDJPY.ecn",
        "EURAUD": "EURAUD.ecn",
        "EURGBP": "EURGBP.ecn",
        "EURNZD": "EURNZD.ecn",
        "AUDNZD": "AUDNZD.ecn",
        "GBPAUD": "GBPAUD.ecn",
        "GBPCAD": "GBPCAD.ecn",
        "GBPNZD": "GBPNZD.ecn",
        "AUDCHF": "AUDCHF.ecn",
        "CADCHF": "CADCHF.ecn",
        "EURCHF": "EURCHF.ecn",
        "GBPCHF": "GBPCHF.ecn",
        "NZDCHF": "NZDCHF.ecn",
        "XAUUSD": "XAUUSD.ecn",
        "XAGUSD": "XAGUSD.ecn",
        "BTCUSD": "BTCUSD.ecn",
        "ETHUSD": "ETHUSD.ecn",
        "SOLUSD": "SOLUSD.ecn",
    },

    # Optional: per-symbol metadata frequently needed in exposure calcs or UI.
    # The engine uses 100000.0 as a default contract size where appropriate.
    # Add or adjust values to match your broker if needed.
    "metadata": {
        "EURUSD": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "GBPUSD": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "USDJPY": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.01},
        "USDCAD": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "USDCHF": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "AUDUSD": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "NZDUSD": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "EURJPY": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.01},
        "GBPJPY": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.01},
        "AUDJPY": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.01},
        "CADJPY": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.01},
        "NZDJPY": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.01},
        "EURAUD": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "EURGBP": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "EURNZD": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "AUDNZD": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "GBPAUD": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "GBPCAD": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "GBPNZD": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "AUDCHF": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "CADCHF": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "EURCHF": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "GBPCHF": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "NZDCHF": {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001},
        "XAUUSD": {"contract_size": 100.0,    "min_lot": 0.01, "pip_size": 0.01},
        "XAGUSD": {"contract_size": 5000.0,   "min_lot": 0.01, "pip_size": 0.001},
        "BTCUSD": {"contract_size": 1.0,      "min_lot": 0.01, "pip_size": 0.1},
        "ETHUSD": {"contract_size": 1.0,      "min_lot": 0.01, "pip_size": 0.01},
        "SOLUSD": {"contract_size": 1.0,      "min_lot": 0.01, "pip_size": 0.01},
    },

    # Map non-USD currencies to a USD conversion pair.
    "currency_to_usd_pair": {
        "AUD": "AUDUSD",
        "EUR": "EURUSD",
        "GBP": "GBPUSD",
        "NZD": "NZDUSD",
        "CAD": "USDCAD",
        "CHF": "USDCHF",
        "JPY": "USDJPY",
    },
}
