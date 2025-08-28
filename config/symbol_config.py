"""
FX-only symbol configuration for trading/execution and exposure calculations.

Notes
-----
- No ATR logic here.
- `symbol_mapping` maps Manager symbols to Terminal symbols (".ecn" suffix used here — adjust to match your broker).
- `currency_to_usd_pair` covers *all currencies used* in the FX list so rc4-style USD consolidation can work.
"""

SYMBOL_CONFIG = {
    # FX symbols we monitor/trade.
    "symbols": [
        "AUDCAD", "AUDJPY", "AUDNZD", "AUDSGD", "AUDCHF", "AUDUSD",
        "CADJPY", "CADCHF",
        "EURAUD", "EURCAD", "EURDKK", "EURGBP", "EURHUF", "EURJPY", "EURNZD", "EURNOK", "EURPLN", "EURSEK", "EURCHF", "EURUSD",
        "GBPAUD", "GBPCAD", "GBPJPY", "GBPNZD", "GBPCHF", "GBPUSD",
        "NZDCAD", "NZDJPY", "NZDCHF", "NZDUSD",
        "CHFDKK", "CHFSGD", "CHFJPY",
        "USDCAD", "USDCNH", "USDCZK", "USDDKK", "USDHKD", "USDHUF", "USDJPY", "USDMXN", "USDNOK", "USDPLN", "USDSGD", "USDZAR", "USDSEK", "USDCHF",
    ],

    # Manager → Terminal mapping (adjust suffixes to your broker's symbols)
    "symbol_mapping": {
        "AUDCAD": "AUDCAD.ecn",
        "AUDJPY": "AUDJPY.ecn",
        "AUDNZD": "AUDNZD.ecn",
        "AUDSGD": "AUDSGD.ecn",
        "AUDCHF": "AUDCHF.ecn",
        "AUDUSD": "AUDUSD.ecn",
        "CADJPY": "CADJPY.ecn",
        "CADCHF": "CADCHF.ecn",
        "EURAUD": "EURAUD.ecn",
        "EURCAD": "EURCAD.ecn",
        "EURDKK": "EURDKK.ecn",
        "EURGBP": "EURGBP.ecn",
        "EURHUF": "EURHUF.ecn",
        "EURJPY": "EURJPY.ecn",
        "EURNZD": "EURNZD.ecn",
        "EURNOK": "EURNOK.ecn",
        "EURPLN": "EURPLN.ecn",
        "EURSEK": "EURSEK.ecn",
        "EURCHF": "EURCHF.ecn",
        "EURUSD": "EURUSD.ecn",
        "GBPAUD": "GBPAUD.ecn",
        "GBPCAD": "GBPCAD.ecn",
        "GBPJPY": "GBPJPY.ecn",
        "GBPNZD": "GBPNZD.ecn",
        "GBPCHF": "GBPCHF.ecn",
        "GBPUSD": "GBPUSD.ecn",
        "NZDCAD": "NZDCAD.ecn",
        "NZDJPY": "NZDJPY.ecn",
        "NZDCHF": "NZDCHF.ecn",
        "NZDUSD": "NZDUSD.ecn",
        "CHFDKK": "CHFDKK.ecn",
        "CHFSGD": "CHFSGD.ecn",
        "CHFJPY": "CHFJPY.ecn",
        "USDCAD": "USDCAD.ecn",
        "USDCNH": "USDCNH.ecn",
        "USDCZK": "USDCZK.ecn",
        "USDDKK": "USDDKK.ecn",
        "USDHKD": "USDHKD.ecn",
        "USDHUF": "USDHUF.ecn",
        "USDJPY": "USDJPY.ecn",
        "USDMXN": "USDMXN.ecn",
        "USDNOK": "USDNOK.ecn",
        "USDPLN": "USDPLN.ecn",
        "USDSGD": "USDSGD.ecn",
        "USDZAR": "USDZAR.ecn",
        "USDSEK": "USDSEK.ecn",
        "USDCHF": "USDCHF.ecn",
    },

    # Metadata (fallbacks; Terminal info takes precedence at runtime)
    "metadata": {
        # Generic FX default: 100k contract, 0.01 min lot, 0.0001 pip
        # JPY-quoted pairs use pip_size 0.01
        **{p: {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.0001} for p in [
            "AUDCAD","AUDNZD","AUDSGD","AUDCHF","AUDUSD","EURAUD","EURCAD","EURDKK","EURGBP","EURHUF","EURNZD","EURNOK","EURPLN","EURSEK","EURCHF","EURUSD",
            "GBPAUD","GBPCAD","GBPNZD","GBPCHF","GBPUSD","NZDCAD","NZDCHF","NZDUSD",
            "CHFDKK","CHFSGD","USDCAD","USDCNH","USDCZK","USDDKK","USDHKD","USDHUF","USDMXN","USDNOK","USDPLN","USDSGD","USDZAR","USDSEK","USDCHF"
        ]},
        **{p: {"contract_size": 100000.0, "min_lot": 0.01, "pip_size": 0.01} for p in [
            "AUDJPY","CADJPY","EURJPY","GBPJPY","NZDJPY","CHFJPY","USDJPY"
        ]},
    },

    # Map every non-USD currency we use to its USD pair
    "currency_to_usd_pair": {
        "AUD": "AUDUSD",
        "CAD": "USDCAD",
        "CHF": "USDCHF",
        "EUR": "EURUSD",
        "GBP": "GBPUSD",
        "JPY": "USDJPY",
	    "CZK": "USDCZK",
	    "DKK": "USDDKK",
	    "HKD": "USDHKD",
	    "HUF": "USDHUF",
	    "MXN": "USDMXN",
	    "NOK": "USDNOK",
	    "PLN": "USDPLN",
	    "SGD": "USDSGD",
	    "ZAR": "USDZAR",	
	    "SEK": "USDSEK"
     },
}
