"""
utils.py
Common helpers used across the trading_algo project (ATR-free).

Exposed functions:
- round_down_to_step(x, step)
- get_min_lot(symbol_info)
- get_contract_size(symbol)
- to_usd_equivalents(net_df, mid_price_fn)

Notes:
- We keep USD conversion simple/transparent for testability. The function
  returns a DataFrame with the same columns that the engine and GUI expect
  (symbol, net_volume, positions, buy_volume, sell_volume). You can later
  extend it to produce true USD exposures if needed.
"""

from __future__ import annotations

import math
from typing import Callable, List, Tuple

import pandas as pd

from config import CONFIG, SYMBOL_CONFIG


# -------------------- Numeric helpers --------------------

def round_down_to_step(x: float, step: float) -> float:
    """
    Floor |x| to the nearest 'step' while preserving sign. If |x| < step, returns 0.0.
    """
    if step is None or step <= 0:
        return float(x)
    ax = abs(float(x))
    if ax < step:
        return 0.0
    units = math.floor(ax / step)
    val = units * step
    return val if x >= 0 else -val


def get_min_lot(symbol_info) -> float:
    """
    Extract min lot from an MT5 symbol_info-like object.
    Falls back to 0.01 if not present.
    """
    try:
        vmin = float(getattr(symbol_info, "volume_min", 0.01))
        return vmin if vmin > 0 else 0.01
    except Exception:
        return 0.01


# -------------------- Symbol metadata --------------------

def get_contract_size(symbol: str) -> float:
    """
    Get per-symbol contract size from SYMBOL_CONFIG; fallback to 100.0.
    """
    try:
        cfg = SYMBOL_CONFIG.get("contract_size", {})
        if symbol in cfg:
            return float(cfg[symbol])
    except Exception:
        pass
    return 100.0


# -------------------- Exposure / USD helpers --------------------

def to_usd_equivalents(
    net_df: pd.DataFrame,
    mid_price_fn: Callable[[str], float],
) -> Tuple[pd.DataFrame, List[dict]]:
    """
    Prepare a DataFrame compatible with engine/GUI processing and return
    lightweight calculation steps for optional CSV export.

    Parameters
    ----------
    net_df : DataFrame
        Expected columns: symbol, net_volume, positions, buy_volume, sell_volume
        (net_volume is in LOTS from Manager).
    mid_price_fn : callable(symbol) -> float
        Mid price getter used for optional annotations in steps.

    Returns
    -------
    (df, steps)
      df: DataFrame with at least the original columns preserved.
      steps: list[dict] with per-symbol notes (symbol, mid_price, contract_size).
    """
    cols = ["symbol", "net_volume", "positions", "buy_volume", "sell_volume"]
    # Ensure missing columns exist
    for c in cols:
        if c not in net_df.columns:
            net_df[c] = 0

    df = net_df[cols].copy()

    steps: List[dict] = []
    for _, r in df.iterrows():
        sym = r["symbol"]
        cs = get_contract_size(sym)
        try:
            mp = float(mid_price_fn(sym)) if mid_price_fn else None
        except Exception:
            mp = None
        steps.append({"symbol": sym, "contract_size": cs, "mid_price": mp})

    return df, steps
