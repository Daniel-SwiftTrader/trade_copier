# indicators/indicators.py

from dataclasses import dataclass
from typing import Optional, Iterable

import pandas as pd
import numpy as np
import MetaTrader5 as mt5

from config import CONFIG, SYMBOL_CONFIG


@dataclass
class TrendMetrics:
    trend: str              # "up" | "down" | "neutral"
    sma_diff: float         # short_sma - long_sma (last value)
    rsi: Optional[float]
    macd: Optional[float]


def _series_from_iter(closes: Iterable[float]) -> pd.Series:
    s = pd.Series(list(closes), dtype="float64")
    # Drop NaNs if any
    return s.dropna()


def _fetch_closes(symbol: str, bars: int = 300) -> pd.Series:
    term_symbol = SYMBOL_CONFIG["symbol_mapping"].get(symbol, symbol)
    # ↓↓↓ Fallback to M1 if M5 doesn’t exist in the stub
    timeframe = getattr(mt5, "TIMEFRAME_M5", None) or getattr(mt5, "TIMEFRAME_M1", 1)
    rates = mt5.copy_rates_from_pos(term_symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        return pd.Series(dtype="float64")
    if isinstance(rates, np.ndarray):
        closes = pd.Series(rates["close"], dtype="float64")
    else:
        closes = pd.Series([r["close"] for r in rates], dtype="float64")
    return closes.dropna()


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=max(2, n // 2)).mean()


def _rsi(s: pd.Series, n: int) -> Optional[float]:
    if len(s) < max(5, n):
        return None
    delta = s.diff()
    up = delta.clip(lower=0.0).rolling(n).mean()
    down = (-delta.clip(upper=0.0)).rolling(n).mean()
    rs = up / (down.replace(0, np.nan))
    out = 100 - (100 / (1 + rs))
    return float(out.iloc[-1]) if len(out) else None


def _macd(s: pd.Series, fast: int, slow: int, signal: int) -> Optional[float]:
    if len(s) < max(fast, slow, signal) + 2:
        return None
    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return float(hist.iloc[-1]) if len(hist) else None


def compute_trend_metrics(symbol: str, closes: Optional[Iterable[float]] = None) -> TrendMetrics:
    """
    Compute trend metrics. If `closes` is None, fetch recent bars from MT5.
    This signature stays compatible with tests that monkeypatch a 1-arg function.
    """
    cfg = CONFIG["indicators"]
    short_n = int(cfg["short_sma_period"])
    long_n = int(cfg["long_sma_period"])
    neutral_eps = float(cfg.get("neutral_trend_threshold", 0.0))

    s = _series_from_iter(closes) if closes is not None else _fetch_closes(symbol)
    if len(s) < max(short_n, long_n):
        # Not enough data → neutral with Nones
        return TrendMetrics(trend="neutral", sma_diff=0.0, rsi=None, macd=None)

    sma_short = _sma(s, short_n)
    sma_long = _sma(s, long_n)
    sma_diff = float((sma_short.iloc[-1] - sma_long.iloc[-1]))

    # Determine trend
    if sma_diff > neutral_eps:
        trend = "up"
    elif sma_diff < -neutral_eps:
        trend = "down"
    else:
        trend = "neutral"

    rsi_val = _rsi(s, int(cfg["rsi_period"]))
    macd_val = _macd(s, int(cfg["macd_fast"]), int(cfg["macd_slow"]), int(cfg["macd_signal"]))

    return TrendMetrics(trend=trend, sma_diff=sma_diff, rsi=rsi_val, macd=macd_val)
