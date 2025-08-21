# trading_algo/main.py

from __future__ import annotations

# Keep absolute imports working whether run as a package (-m trading_algo.main)
# or as a script (python trading_algo/main.py)
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import time
from typing import Callable, Dict, Any, List

from config import CONFIG, SYMBOL_CONFIG
from trade_logging import get_logger, log_json, log_exception
from data_access.data_access import ManagerClient, TerminalClient
from trade_logic.engine import TradingEngine
from gui.gui import run_gui


# ------------------------ Manager helper ------------------------

def _parse_host_port(server: str) -> tuple[str, int]:
    s = (server or "").strip()
    if ":" in s:
        h, p = s.rsplit(":", 1)
        try:
            return h, int(p)
        except ValueError:
            return h, 443
    return s or "localhost", 443


def build_manager_rows_provider(logger) -> Callable[[], List[Dict[str, Any]]]:
    """
    Connects to MT5 Manager via MT5Manager.ManagerAPI and returns a callable
    that fetches per-symbol net positions in LOTS using ManagerClient.get_net_positions().
    Falls back to an empty provider if import/connect fails.
    """
    try:
        import MT5Manager
    except Exception as e:
        log_exception(logger, e, where="manager_import", note="MT5Manager not importable")
        return lambda: []

    m_server = str(CONFIG["connection"].get("manager_server", ""))
    m_login = int(CONFIG["connection"].get("manager_login", 0))
    m_pass  = str(CONFIG["connection"].get("manager_password", ""))
    host, port = _parse_host_port(m_server)

    def _provider():
        manager = None
        try:
            manager = MT5Manager.ManagerAPI()
            log_json(logger, event="manager_connect_attempt", host=host, port=port, login=m_login)

            ok = manager.Connect(
                host,
                m_login,
                m_pass,
                MT5Manager.ManagerAPI.EnPumpModes.PUMP_MODE_POSITIONS.value,
                30000,  # ms timeout
            )
            if not ok:
                log_json(logger, event="manager_connect_failed")
                return []

            # brief wait for internal pumps 
            wait_s = int(CONFIG.get("runtime", {}).get("manager_wait_seconds", 5))
            time.sleep(max(0, wait_s))


            rows = ManagerClient().get_net_positions(manager)
            log_json(logger, event="manager_fetch_ok", rows=len(rows))
            return rows or []
        except Exception as e:
            log_exception(logger, e, where="manager_fetch")
            return []
        finally:
            try:
                if manager:
                    manager.Disconnect()
                    log_json(logger, event="manager_disconnected")
            except Exception:
                pass

    return _provider


# ------------------------ Engine / CLI ------------------------

def build_engine() -> TradingEngine:
    logger = get_logger("main")

    # Terminal login
    term = TerminalClient()
    if not term.init_and_login():
        raise SystemExit("MT5 Terminal login failed. Check CONFIG['connection'] credentials & server.")

    # Manager provider
    manager_rows_provider = build_manager_rows_provider(logger)

    # Engine wires the provider + terminal
    engine = TradingEngine(manager_rows_provider, term)
    log_json(logger, event="engine_built")
    return engine


def run_headless(engine: TradingEngine, *, once: bool, interval: int, execute: bool) -> None:
    """
    Our engine performs decisions and execution inside cycle().
    - If execute=True: place orders (normal path)
    - If execute=False: we just run cycle() and rely on config to gate execution (optional)
      (For a true dry-run, set your config to block trades or we can add a dry-run toggle in engine.)
    """
    log = get_logger("main")
    try:
        while True:
            out = engine.cycle() if execute else engine.cycle()  # same today; engine handles gating
            log_json(log, event="cycle_done", trades=out.get("trades_executed", 0), status=out.get("status"))
            if once:
                break
            time.sleep(max(1, int(interval)))
    except KeyboardInterrupt:
        print("Interrupted — exiting…")
    except Exception as e:
        log_exception(log, e, where="headless_loop")
        raise

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Trading Algo (ATR-free)")
    ap.add_argument("--headless", action="store_true", help="run without GUI")
    ap.add_argument("--once", action="store_true", help="headless: run a single cycle and exit")
    ap.add_argument("--execute", action="store_true", help="headless: place orders during the cycle")
    ap.add_argument("--interval", type=int, default=None,  # ← let config decide if None
                    help="headless: seconds between cycles (default from config.runtime.cycle_seconds)")
    return ap.parse_args()



def main() -> None:
    args = parse_args()
    engine = build_engine()

    # Resolve cycle interval: CLI overrides config
    cfg_interval = int(CONFIG.get("runtime", {}).get("cycle_seconds", 5))
    interval = args.interval if args.interval is not None else cfg_interval

    if args.headless:
        run_headless(engine, once=args.once, interval=interval, execute=args.execute)
    else:
        # Use config for GUI refresh
        run_gui(engine, refresh_seconds=cfg_interval)



if __name__ == "__main__":
    main()
