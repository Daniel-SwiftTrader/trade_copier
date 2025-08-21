"""
Core trading engine:
- Manager net positions -> USD-equivalent exposure
- Delta to target -> execution (market or partial-limit, ATR-free)
- Risk guard: daily loss block, optional auto-close when breached
- CSV logs compatible with rc4, plus GUI-friendly rows (including PNL)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, List, Any, Tuple
import time
import os

import MetaTrader5 as mt5
import pandas as pd

from config import CONFIG, SYMBOL_CONFIG
from data_access.data_access import TerminalClient
from trade_logging.logger import (
    write_exposure_tables, log_trade_csv, log_rejected_csv,
    log_account_metrics_csv, write_daily_summary_csv,
)
# Try to import the rc4-style audit CSV writer; if missing, no-op so engine still runs.
try:  # pragma: no cover
    from trade_logging.logger import write_currency_exposure_calculations
except Exception:  # pragma: no cover
    def write_currency_exposure_calculations(*_args, **_kwargs):
        return None

from utils.utils import (
    round_down_to_step, to_usd_equivalents
)
from indicators.indicators import compute_trend_metrics


# -------------------- helpers that respect SYMBOL_CONFIG --------------------

def _split_ccy_pair(sym: str) -> Tuple[str, str]:
    """'EURJPY' -> ('EUR','JPY'); 'XAUUSD' -> ('XAU','USD'); fallback to (SYM,'USD')."""
    s = sym.upper()
    if len(s) >= 6:
        return s[:3], s[3:6]
    return s, "USD"


def _inv_price(p: float | None) -> float | None:
    return (1.0 / p) if p and p > 0 else None


# -------------------- data classes --------------------

@dataclass
class DecisionRow:
    symbol: str
    positions: int
    buy_volume: float
    sell_volume: float
    current_net: float
    current_position: float
    target_position: float
    delta_position: float
    trend_signal: str
    trend_strength: float
    rsi: float | None
    macd: float | None
    reason: str
    pnl: float


# -------------------- engine --------------------

class TradingEngine:
    def __init__(self, manager_rows_provider, terminal: TerminalClient):
        """
        manager_rows_provider: callable -> list[dict] of manager exposures (lots)
        terminal: TerminalClient instance
        """
        self._get_manager_rows = manager_rows_provider
        self.term = terminal

        # Tradable universe strictly from symbol_config
        self._tradable = set(SYMBOL_CONFIG.get("symbols", []))
        self._map = SYMBOL_CONFIG.get("symbol_mapping", {})
        self._c2u = SYMBOL_CONFIG.get("currency_to_usd_pair", {})
        self._meta = SYMBOL_CONFIG.get("metadata", {})

    # -------- terminal/symbol helpers (use symbol_config mapping) --------

    def _mid_price(self, pair: str) -> float | None:
        """Mid for a manager/engine symbol using terminal mapping."""
        tsym = self._map.get(pair, pair)
        return self.term.get_mid_price(tsym)

    def _symbol_info(self, symbol: str):
        """Terminal symbol_info using mapping."""
        return self.term.symbol_info(self._map.get(symbol, symbol))

    def _price_and_point(self, symbol: str):
        tsym = self._map.get(symbol, symbol)
        info = self.term.symbol_info(tsym)
        tick = self.term.symbol_info_tick(tsym)
        if not info or not tick:
            return None, None, None
        price = tick.ask if tick.ask > 0 else (tick.bid or 0)
        return price, info.point, info.digits

    def _current_position(self, symbol: str) -> float:
        return self.term.get_current_position(symbol)

    # ---- metadata fallbacks from SYMBOL_CONFIG ----

    def _min_lot_with_fallback(self, symbol: str) -> float:
        """Get min lot from terminal; fallback to symbol_config metadata."""
        info = self._symbol_info(symbol)
        if info:
            try:
                return float(info.volume_min)
            except Exception:
                pass
        return float(self._meta.get(symbol, {}).get("min_lot", 0.01))

    def _contract_size_for(self, symbol: str) -> float:
        """Contract size from symbol_config metadata if present; else 100k for FX."""
        return float(self._meta.get(symbol, {}).get("contract_size", 100000.0))

    # -------- Risk & Metrics --------

    def _account_metrics(self) -> dict:
        ai = mt5.account_info()
        metrics = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "balance": round(ai.balance, 2) if ai else 0.0,
            "equity": round(ai.equity, 2) if ai else 0.0,
            "margin": round(ai.margin, 2) if ai else 0.0,
            "free_margin": round((ai.equity - ai.margin), 2) if ai else 0.0,
            "margin_level": round(ai.margin_level, 2) if (ai and ai.margin > 0) else 0.0
        }
        return metrics

    def _todays_realized_pnl(self) -> float:
        start_of_day = datetime.combine(date.today(), datetime.min.time()).timestamp()
        deals = mt5.history_deals_get(start_of_day, time.time())
        if not deals:
            return 0.0
        return sum(d.profit for d in deals)

    def _unrealized_pnl(self) -> float:
        ai = mt5.account_info()
        return ai.profit if ai else 0.0

    def _check_daily_loss(self) -> tuple[bool, float]:
        realized = self._todays_realized_pnl()
        limit = CONFIG["risk_management"]["daily_loss_limit"]
        return (realized >= limit, realized)

    # -------- Execution --------

    def _send_market_or_partial_limit(self, symbol: str, side_buy: bool, volume: float) -> bool:
        tsym = self._map.get(symbol, symbol)
        info = self.term.symbol_info(tsym)
        tick = self.term.symbol_info_tick(tsym)
        if not info or not tick:
            return False

        market_price = tick.ask if side_buy else tick.bid
        requests = []
        if CONFIG["limit_orders"]["use_limit_orders"] and CONFIG["limit_orders"]["enable_partial_limit"]:
            mkt_vol = round_down_to_step(volume * CONFIG["limit_orders"]["market_order_percentage"], info.volume_step)
            lim_vol = round_down_to_step(volume - mkt_vol, info.volume_step)
            if mkt_vol >= info.volume_min:
                requests.append(dict(
                    action=mt5.TRADE_ACTION_DEAL,
                    symbol=tsym,
                    volume=mkt_vol,
                    type=mt5.ORDER_TYPE_BUY if side_buy else mt5.ORDER_TYPE_SELL,
                    price=market_price,
                    deviation=10, magic=123456,
                    type_time=mt5.ORDER_TIME_GTC, type_filling=mt5.ORDER_FILLING_IOC
                ))
            if lim_vol >= info.volume_min:
                offset = CONFIG["limit_orders"]["limit_offset_points"] * info.point
                limit_price = (tick.bid - offset) if side_buy else (tick.ask + offset)
                requests.append(dict(
                    action=mt5.TRADE_ACTION_PENDING,
                    symbol=tsym,
                    volume=lim_vol,
                    type=mt5.ORDER_TYPE_BUY_LIMIT if side_buy else mt5.ORDER_TYPE_SELL_LIMIT,
                    price=round(limit_price, info.digits),
                    deviation=10, magic=123456,
                    type_time=mt5.ORDER_TIME_GTC, type_filling=mt5.ORDER_FILLING_IOC
                ))
        else:
            requests.append(dict(
                action=mt5.TRADE_ACTION_DEAL,
                symbol=tsym,
                volume=volume,
                type=mt5.ORDER_TYPE_BUY if side_buy else mt5.ORDER_TYPE_SELL,
                price=market_price,
                deviation=10, magic=123456,
                type_time=mt5.ORDER_TIME_GTC, type_filling=mt5.ORDER_FILLING_IOC
            ))

        success_any = False
        for req in requests:
            res = self.term.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                success_any = True
            else:
                log_rejected_csv({
                    "symbol": symbol,
                    "reason": f"order_send failed: {getattr(res,'comment', 'no result')}",
                    "delta_position": req["volume"] if side_buy else -req["volume"],
                    "current_position": self._current_position(symbol),
                    "current_net": 0.0,
                    "trend_signal": "",
                    "trend_strength": 0.0,
                    "rsi": None,
                    "macd": None,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
        return success_any

    def _close_all_positions(self) -> int:
        positions = self.term.positions_get()
        if not positions:
            return 0
        closed = 0
        for pos in positions:
            side_buy = (pos.type == mt5.POSITION_TYPE_BUY)
            req = dict(
                action=mt5.TRADE_ACTION_DEAL,
                symbol=pos.symbol,
                volume=pos.volume,
                type=mt5.ORDER_TYPE_SELL if side_buy else mt5.ORDER_TYPE_BUY,
                position=pos.ticket,
                price=self.term.symbol_info_tick(pos.symbol).bid if side_buy else self.term.symbol_info_tick(pos.symbol).ask,
                deviation=20, magic=123456,
                type_time=mt5.ORDER_TIME_GTC, type_filling=mt5.ORDER_FILLING_IOC
            )
            res = self.term.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                closed += 1
        return closed

    # -------------------- USD consolidation (rc4-style) --------------------

    def _compute_usd_pairs_from_currency_exposures(
        self, net_df: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[dict]]:
        """
        rc4-style consolidation:
        1) Sum currency exposures in units:
           base += L*contract_size; quote += -L*contract_size*mid
        2) For each non-USD currency C, map to USD pair via SYMBOL_CONFIG["currency_to_usd_pair"][C]
           If USD/C: current_net = -net_units / (contract_size(pair)*mid(pair))
           If C/USD: current_net =  net_units /  contract_size(pair)
        Returns (usd_df, calculation_steps).
        """
        from collections import defaultdict

        ccy_units: Dict[str, float] = defaultdict(float)
        steps: list[dict] = []

        # 1) accumulate currency exposures
        for _, r in net_df.iterrows():
            sym = str(r["symbol"]).upper()
            lots = float(r.get("net_volume", 0.0))
            step = {"symbol": sym, "net_volume": lots}

            # Only process 6-char alpha pairs; metals/crypto also fit (XAUUSD, BTCUSD)
            if len(sym) != 6 or not sym.isalpha():
                step.update({
                    "base_exposure": 0.0, "quote_exposure": 0.0,
                    "aggregated_net_units": 0.0, "current_net": 0.0,
                    "formula": "N/A (non-forex)"
                })
                steps.append(step)
                continue

            base, quote = sym[:3], sym[3:]
            cs = self._contract_size_for(sym)
            mid = self._mid_price(sym)
            if mid is None:
                step.update({
                    "base_exposure": 0.0, "quote_exposure": 0.0,
                    "aggregated_net_units": 0.0, "current_net": 0.0,
                    "formula": "N/A (no mid price)"
                })
                steps.append(step)
                continue

            base_exp = lots * cs
            quote_exp = -lots * cs * mid
            ccy_units[base] += base_exp
            ccy_units[quote] += quote_exp
            step.update({"base_exposure": base_exp, "quote_exposure": quote_exp})
            steps.append(step)

        # 2) express each non-USD currency in a single USD pair
        rows: list[dict] = []
        for C, net_units in ccy_units.items():
            if C == "USD":
                steps.append({
                    "symbol": None, "net_volume": 0.0,
                    "base_exposure": 0.0, "quote_exposure": 0.0,
                    "aggregated_net_units": net_units, "current_net": 0.0,
                    "formula": "N/A (no USD pair)"
                })
                continue

            pair = self._c2u.get(C)
            if not pair:
                steps.append({
                    "symbol": None, "net_volume": 0.0,
                    "base_exposure": 0.0, "quote_exposure": 0.0,
                    "aggregated_net_units": net_units, "current_net": 0.0,
                    "formula": "N/A (no USD pair)"
                })
                continue

            mid = self._mid_price(pair)
            cs_pair = self._contract_size_for(pair)
            if mid is None:
                steps.append({
                    "symbol": pair, "net_volume": 0.0,
                    "base_exposure": 0.0, "quote_exposure": 0.0,
                    "aggregated_net_units": net_units, "current_net": 0.0,
                    "formula": "N/A (no mid price)"
                })
                continue

            if pair.startswith("USD"):  # USD/C
                current_net = -net_units / (cs_pair * mid)
                formula = f"-net_units ({net_units}) / (contract_size ({cs_pair}) * mid_price ({mid}))"
            else:                        # C/USD
                current_net = net_units / cs_pair
                formula = f"net_units ({net_units}) / contract_size ({cs_pair})"

            steps.append({
                "symbol": pair, "net_volume": 0.0,
                "base_exposure": 0.0, "quote_exposure": 0.0,
                "aggregated_net_units": net_units,
                "current_net": current_net, "formula": formula
            })

            # build trading row (only if symbol is tradable in SYMBOL_CONFIG)
            if pair in self._tradable:
                rows.append({
                    "symbol": pair,
                    "net_volume": float(current_net),
                    "positions": 0, "buy_volume": 0.0, "sell_volume": 0.0,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

        usd_df = pd.DataFrame(rows, columns=["symbol", "net_volume", "positions", "buy_volume", "sell_volume", "timestamp"])
        return usd_df, steps

    # -------------------- Main cycle --------------------

    def cycle(self) -> dict:
        """
        Run one decision/execute cycle and return GUI-friendly payload:
          { "usd_rows": [...], "pair_rows": [...], "trades_executed": int, "status"?: str }
        """
        # 1) Read manager exposures
        manager_rows = self._get_manager_rows()
        if not manager_rows:
            return {"usd_rows": [], "pair_rows": [], "trades_executed": 0}

        # Pair table: always show original manager view
        pair_rows = [
            {"Symbol": r["symbol"], "Trades": int(r.get("positions", 0)),
             "Long": float(r.get("buy_volume", 0.0)),
             "Short": float(r.get("sell_volume", 0.0)),
             "Net Position": float(r.get("net_volume", 0.0))}
            for r in manager_rows
        ]

        # 2) Consolidation and/or USD conversion
        routing = CONFIG.get("routing", {})
        if routing.get("consolidate_to_usd", False):
            # Build USD pairs directly from currency exposures (rc4-style)
            net_df = pd.DataFrame(manager_rows)
            usd_df, calc_steps = self._compute_usd_pairs_from_currency_exposures(net_df)
            # Overwrite audit file each cycle
            try:
                write_currency_exposure_calculations(calc_steps, os.getcwd())
            except Exception:
                pass
        else:
            # No consolidation: operate on manager rows and convert to USD equivalents
            trade_rows = manager_rows
            net_df = pd.DataFrame(trade_rows)
            usd_df, _ = to_usd_equivalents(net_df, self._mid_price)

        # 3) Risk check (daily loss)
        ok, realized = self._check_daily_loss()
        unreal = self._unrealized_pnl()
        if not ok:
            if CONFIG["risk_management"].get("auto_close_on_daily_loss_limit", False):
                self._close_all_positions()
            metrics = self._account_metrics()
            metrics.update({"realized_pnl_today": realized, "unrealized_pnl": unreal})
            log_account_metrics_csv(metrics)
            write_daily_summary_csv({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "total_trades": 0,
                "avg_slippage_points": 0.0,
                "buy_trades": 0,
                "sell_trades": 0,
                "win_trades": 0,
                "loss_trades": 0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "unrealized_pnl": unreal,
                "realized_pnl": realized
            })
            write_exposure_tables(usd_df, os.getcwd())
            return {"usd_rows": [], "pair_rows": pair_rows, "trades_executed": 0, "status": "RISK GUARD: daily loss breached"}

        # 4) Decide & execute per (possibly consolidated) USD symbol
        trades_executed = 0
        gui_usd_rows: list[dict] = []

        for _, row in usd_df.iterrows():
            symbol = row["symbol"]
            current_net = float(row["net_volume"])
            positions = int(row.get("positions", 0))
            buy_vol = float(row.get("buy_volume", 0.0))
            sell_vol = float(row.get("sell_volume", 0.0))
            current_pos = self._current_position(symbol)

            # Target/Delta (ATR-free)
            mult = CONFIG["trade_management"]["fixed_multiplier"] if CONFIG["trade_management"]["use_fixed_multiplier"] \
                   else CONFIG["trade_management"]["trade_size_multiplier"]
            target = -current_net * mult
            delta = target - current_pos

            # Round DOWN to symbol's min lot (terminal -> fallback to symbol_config)
            min_lot = self._min_lot_with_fallback(symbol)
            delta = round_down_to_step(delta, min_lot)

            # Trend metrics + gating
            tm = compute_trend_metrics(symbol)
            allow = True
            if tm.trend == "neutral" and not CONFIG["trade_management"]["allow_trades_on_neutral_trend"]:
                allow = False
            if tm.trend in ("down",) and target > current_pos and not CONFIG["trade_management"]["allow_trades_on_opposite_trend"]:
                allow = False
            if tm.trend in ("up",) and target < current_pos and not CONFIG["trade_management"]["allow_trades_on_opposite_trend"]:
                allow = False

            reason = "Initialized"
            if abs(delta) < min_lot:
                reason = f"Delta too small: {delta:.2f}"
                executed = False
            elif not allow:
                reason = "Trade conditions not met"
                executed = False
                log_rejected_csv({
                    "symbol": symbol,
                    "reason": reason,
                    "delta_position": delta,
                    "current_position": current_pos,
                    "current_net": current_net,
                    "trend_signal": tm.trend,
                    "trend_strength": tm.sma_diff,
                    "rsi": tm.rsi,
                    "macd": tm.macd,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            else:
                # clamp to max position size
                new_pos = current_pos + (abs(delta) if delta > 0 else -abs(delta))
                if abs(new_pos) > CONFIG["trade_management"]["max_position_size"]:
                    reason = "Exceeds max position size"
                    executed = False
                    log_rejected_csv({
                        "symbol": symbol,
                        "reason": reason,
                        "delta_position": delta,
                        "current_position": current_pos,
                        "current_net": current_net,
                        "trend_signal": tm.trend,
                        "trend_strength": tm.sma_diff,
                        "rsi": tm.rsi,
                        "macd": tm.macd,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                else:
                    executed = self._send_market_or_partial_limit(symbol, side_buy=(delta > 0), volume=abs(delta))
                    reason = "Trade executed" if executed else "Trade failed"
                    if executed:
                        trades_executed += 1
                        price, point, digits = self._price_and_point(symbol)
                        log_trade_csv({
                            "symbol": symbol,
                            "terminal_symbol": self._map.get(symbol, symbol),
                            "trade_type": "BUY" if delta > 0 else "SELL",
                            "requested_volume": abs(delta),
                            "executed_volume": abs(delta),
                            "requested_price": price,
                            "executed_price": price,
                            "slippage_points": 0,
                            "current_net": current_net,
                            "target_position": target,
                            "current_position": current_pos,
                            "delta_position": delta,
                            "trend_signal": tm.trend,
                            "trend_strength": tm.sma_diff,
                            "rsi": tm.rsi,
                            "macd": tm.macd,
                            "reason": reason,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "order_id": ""
                        })

            # per-symbol PnL (live)
            sym_term = self._map.get(symbol, symbol)
            sym_positions = mt5.positions_get(symbol=sym_term) or []
            sym_pnl = sum(p.profit for p in sym_positions)

            gui_usd_rows.append({
                "Symbol": symbol,
                "Net USD Position": f"{current_net:.2f}",
                "Trade Position": f"{current_pos:.2f}",
                "Target Position": f"{target:.2f}",
                "Trade Delta": f"{delta:.2f}",
                "Trend": tm.trend.capitalize(),
                "Trend Strength": tm.sma_diff,
                "RSI": None if tm.rsi is None else round(tm.rsi, 2),
                "MACD": None if tm.macd is None else round(tm.macd, 4),
                "Reason": reason,
                "PNL": round(sym_pnl, 2)
            })

        # 5) Exposure tables like rc4
        write_exposure_tables(usd_df, os.getcwd())

        # 6) Metrics + daily summary snapshot
        metrics = self._account_metrics()
        metrics.update({"realized_pnl_today": self._todays_realized_pnl(), "unrealized_pnl": unreal})
        log_account_metrics_csv(metrics)
        write_daily_summary_csv({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_trades": trades_executed,
            "avg_slippage_points": 0.0,
            "buy_trades": 0,
            "sell_trades": 0,
            "win_trades": 0,
            "loss_trades": 0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "unrealized_pnl": unreal,
            "realized_pnl": self._todays_realized_pnl()
        })

        return {
            "usd_rows": gui_usd_rows,
            "pair_rows": pair_rows,
            "trades_executed": trades_executed
        }
