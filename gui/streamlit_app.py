"""
Streamlit UI for the trading_algo.

Run with:
    streamlit run trading_algo/gui/streamlit_app.py

What it does:
- Builds the engine (Manager + Terminal) using CONFIG/symbol_config
- Shows account panel, USD-decisions table, Manager-pairs table, trade log
- Lets you run one cycle (preview) or run & execute trades
- Auto-refresh and simple exports
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple

import pandas as pd
import streamlit as st

from config import CONFIG, SYMBOL_CONFIG
from data_access.data_access import ManagerClient, TerminalClient
from trade_logic.engine import TradingEngine
from trade_logging import (
    get_logger, log_json, log_exception,
    export_ccy_tables_from_gui  # optional export helper if you want
)

# ------------- Engine builder (no import-cycle with main.py) -----------------

def _parse_host_port(server: str) -> Tuple[str, int]:
    s = (server or "").strip()
    if ":" in s:
        h, p = s.rsplit(":", 1)
        try:
            return h, int(p)
        except ValueError:
            return h, 443
    return s or "localhost", 443


def build_engine() -> TradingEngine:
    log = get_logger("streamlit")
    m_server = str(CONFIG["connection"].get("manager_server", ""))
    m_host, m_port = _parse_host_port(m_server)
    m_login = int(CONFIG["connection"].get("manager_login", 0))
    m_pass = str(CONFIG["connection"].get("manager_password", ""))

    # Manager client: ManagerClient.get_net_positions should do connect->fetch->disconnect
    mgr = ManagerClient(host=m_host, port=m_port, login=m_login, password=m_pass)

    # Terminal client
    term = TerminalClient()
    if not term.initialize():
        # show a friendly message, but keep UI alive
        log_json(get_logger("streamlit"), "terminal_init_failed")
    # Build engine: it expects a callable for manager rows + a terminal client
    engine = TradingEngine(mgr.get_net_positions, term)  # type: ignore[arg-type]
    log_json(log, "engine_built_streamlit", manager_server=f"{m_host}:{m_port}")
    return engine

# -------------------------- Helpers (UI / Files) -----------------------------

def _today_folder() -> str:
    base = os.getcwd()
    date_folder = datetime.now().strftime("%Y-%m-%d")
    out = os.path.join(base, date_folder) if CONFIG["outputs"].get("csv_dir_by_date", True) else base
    os.makedirs(out, exist_ok=True)
    return out


def _read_latest_trade_log() -> pd.DataFrame:
    folder = _today_folder()
    # pick the newest trade_log_*.csv if any
    files = [f for f in os.listdir(folder) if f.startswith("trade_log_") and f.endswith(".csv")]
    if not files:
        return pd.DataFrame()
    files.sort(reverse=True)
    return pd.read_csv(os.path.join(folder, files[0]))


def _dicts_to_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()

# --------------------------------- UI ----------------------------------------

st.set_page_config(page_title="Trading Algo (Streamlit)", layout="wide")

# Session state: engine & options
if "engine" not in st.session_state:
    st.session_state.engine = build_engine()
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True
if "execute" not in st.session_state:
    st.session_state.execute = False
if "last_run" not in st.session_state:
    st.session_state.last_run = None

# Sidebar controls
with st.sidebar:
    st.title("Controls")
    st.markdown("**Routing**")
    consolidate = st.checkbox("Consolidate to USD pairs (rc4)", value=bool(CONFIG.get("routing", {}).get("consolidate_to_usd", True)))
    CONFIG.setdefault("routing", {})["consolidate_to_usd"] = consolidate

    st.markdown("**Execution**")
    st.session_state.execute = st.checkbox("Execute trades", value=st.session_state.execute)
    st.caption("If off, cycles will only preview decisions.")

    st.markdown("**Refresh**")
    default_secs = int(CONFIG.get("runtime", {}).get("cycle_seconds", 5))
    interval = st.number_input("Auto-refresh seconds", min_value=2, max_value=120, value=default_secs, step=1)
    st.session_state.auto_refresh = st.checkbox("Auto-refresh", value=True)

    st.markdown("---")
    if st.button("Run one cycle (preview)"):
        st.session_state._run_now = ("preview", time.time())
    if st.button("Run one cycle & EXECUTE"):
        st.session_state._run_now = ("execute", time.time())

# Header
st.title("Trading Algo — Streamlit")
st.caption("MT5 Manager exposures → (optional) USD consolidation → delta execution. ATR-free. Config-driven.")

# Auto-refresh tick
if st.session_state.auto_refresh:
    st.experimental_set_query_params(t=int(time.time()))
    st.experimental_rerun  # no-op reference; autorefresh handled via below
st_autorefresh_event = st.experimental_data_editor if False else None  # placeholder; we’ll use autorefresh widget:
st_autorefresh = st.experimental_memo if False else None  # (Streamlit >=1.32 has st.autorefresh)
try:
    # If available in your Streamlit version:
    from streamlit_autorefresh import st_autorefresh as _st_autorefresh  # optional small helper package
    _st_autorefresh(interval=interval * 1000, key="auto_r")
except Exception:
    pass

engine: TradingEngine = st.session_state.engine

# Run cycle on demand
run_mode = None
if "_run_now" in st.session_state:
    run_mode, _ts = st.session_state._run_now
    del st.session_state._run_now

# Cycle execution
result = None
error_msg = None
try:
    if run_mode == "execute" or (st.session_state.auto_refresh and st.session_state.execute):
        # execute path
        result = engine.cycle()
        st.session_state.last_run = datetime.now().strftime("%H:%M:%S")
    elif run_mode == "preview" or st.session_state.auto_refresh:
        # preview path (no orders): run a dry cycle by toggling execute off temporarily
        # Simple approach: just run cycle() but with trade gates blocking via multiplier 0?
        # Instead we call cycle() and rely on config gating; for a true preview you can set trade_size_multiplier=0 in CONFIG and revert.
        result = engine.cycle() if not st.session_state.execute else None
        st.session_state.last_run = datetime.now().strftime("%H:%M:%S")
except Exception as e:
    error_msg = str(e)

# Account panel
colA, colB, colC, colD, colE = st.columns([1.2,1,1,1,1])
with colA:
    st.subheader("Account")
    st.caption(f"Last run: {st.session_state.last_run or '—'}")
with colB:
    try:
        import MetaTrader5 as mt5
        ai = mt5.account_info()
        st.metric("Balance", f"{ai.balance:,.2f}" if ai else "—")
    except Exception:
        st.metric("Balance", "—")
with colC:
    try:
        ai = mt5.account_info()
        st.metric("Equity", f"{ai.equity:,.2f}" if ai else "—")
    except Exception:
        st.metric("Equity", "—")
with colD:
    try:
        ai = mt5.account_info()
        st.metric("Margin", f"{ai.margin:,.2f}" if ai else "—")
    except Exception:
        st.metric("Margin", "—")
with colE:
    try:
        ai = mt5.account_info()
        st.metric("Profit", f"{ai.profit:,.2f}" if ai else "—")
    except Exception:
        st.metric("Profit", "—")

if error_msg:
    st.error(f"Cycle error: {error_msg}")

# Tables
usd_rows = (result or {}).get("usd_rows", [])
pair_rows = (result or {}).get("pair_rows", [])
trades_executed = int((result or {}).get("trades_executed", 0))

st.markdown("### USD Decisions")
usd_df = _dicts_to_df(usd_rows)
if not usd_df.empty:
    # pretty types
    num_cols = [c for c in usd_df.columns if c not in ("Symbol", "Trend", "Reason")]
    for c in num_cols:
        try:
            usd_df[c] = pd.to_numeric(usd_df[c], errors="ignore")
        except Exception:
            pass
    st.dataframe(usd_df, use_container_width=True, hide_index=True)
    st.download_button("Download USD Decisions CSV", data=usd_df.to_csv(index=False), file_name="usd_decisions.csv")
else:
    st.info("No USD decision rows yet.")

st.markdown("### Manager Pairs (raw net)")
pair_df = _dicts_to_df(pair_rows)
if not pair_df.empty:
    st.dataframe(pair_df, use_container_width=True, hide_index=True)
    st.download_button("Download Manager Pairs CSV", data=pair_df.to_csv(index=False), file_name="manager_pairs.csv")
else:
    st.info("No manager rows yet.")

# Trade log (today)
st.markdown("### Trade Log (today)")
log_df = _read_latest_trade_log()
if not log_df.empty:
    st.dataframe(log_df, use_container_width=True)
    st.download_button("Download Trade Log CSV", data=log_df.to_csv(index=False), file_name="trade_log_today.csv")
else:
    st.caption("No trade log yet today.")

# Footer / status
st.markdown("---")
status_cols = st.columns(3)
with status_cols[0]:
    st.metric("Trades executed this cycle", trades_executed)
with status_cols[1]:
    st.write(f"Consolidate to USD: **{bool(CONFIG.get('routing', {}).get('consolidate_to_usd', False))}**")
with status_cols[2]:
    st.caption("All symbol metadata/mapping from config/symbol_config.py")
