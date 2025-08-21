# trading_algo/trade_logging/logger.py

import os
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import pandas as pd
from config import CONFIG, SYMBOL_CONFIG


# ---------- Filenames / prefixes ----------
TRADE_LOG_PREFIX = "trade_log"
REJECTED_TRADE_LOG_PREFIX = "rejected_trade_log"
SUMMARY_FILE_PREFIX = "daily_summary"
ACCOUNT_METRICS_PREFIX = "account_metrics"
OUTPUT_FILE = "exposure_net_positions.csv"
PREV_FILE = "previous_net_positions.csv"


# ---------- Folder helper ----------
def _date_folder(base_dir: str | None = None) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    root = base_dir or os.getcwd()
    folder = os.path.join(root, date_str)
    os.makedirs(folder, exist_ok=True)
    return folder


# ---------- Exposure tables (rc4 style) ----------
def write_exposure_tables(usd_df: pd.DataFrame, base_dir: str | None = None) -> None:
    folder = _date_folder(base_dir)
    usd_df.to_csv(os.path.join(folder, OUTPUT_FILE), index=False)
    usd_df.to_csv(os.path.join(folder, PREV_FILE), index=False)


# ---------- CSV loggers (rc4 style) ----------
def log_trade_csv(row: dict, base_dir: str | None = None) -> None:
    folder = _date_folder(base_dir)
    fpath = os.path.join(folder, f"{TRADE_LOG_PREFIX}_{datetime.now().strftime('%Y-%m-%d')}.csv")
    df = pd.DataFrame([row])
    header = not os.path.exists(fpath)
    df.to_csv(fpath, mode="a", header=header, index=False)


def log_rejected_csv(row: dict, base_dir: str | None = None) -> None:
    folder = _date_folder(base_dir)
    fpath = os.path.join(folder, f"{REJECTED_TRADE_LOG_PREFIX}_{datetime.now().strftime('%Y-%m-%d')}.csv")
    df = pd.DataFrame([row])
    header = not os.path.exists(fpath)
    df.to_csv(fpath, mode="a", header=header, index=False)


def log_account_metrics_csv(metrics: dict, base_dir: str | None = None) -> None:
    folder = _date_folder(base_dir)
    fpath = os.path.join(folder, f"{ACCOUNT_METRICS_PREFIX}_{datetime.now().strftime('%Y-%m-%d')}.csv")
    df = pd.DataFrame([metrics])
    header = not os.path.exists(fpath)
    df.to_csv(fpath, mode="a", header=header, index=False)


def write_daily_summary_csv(summary: dict, base_dir: str | None = None) -> None:
    folder = _date_folder(base_dir)
    fpath = os.path.join(folder, f"{SUMMARY_FILE_PREFIX}_{datetime.now().strftime('%Y-%m-%d')}.csv")
    pd.DataFrame([summary]).to_csv(fpath, index=False)


def export_ccy_tables_from_gui(usd_rows: list[dict], pair_rows: list[dict], base_dir: str | None = None) -> None:
    folder = _date_folder(base_dir)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    if usd_rows:
        pd.DataFrame(usd_rows).to_csv(os.path.join(folder, f"ccy_usd_positions_{ts}.csv"), index=False)
    if pair_rows:
        pd.DataFrame(pair_rows).to_csv(os.path.join(folder, f"ccy_pair_positions_{ts}.csv"), index=False)


# Overwrite-each-cycle currency exposure audit (rc4-style)
CURRENCY_EXPOSURE_CALC_FILE = "currency_exposure_calculations.csv"

def write_currency_exposure_calculations(steps, base_dir: str | None = None) -> None:
    """
    Overwrite a CSV with the per-symbol currency→USD consolidation math.
    Accepts a pandas DataFrame or an iterable of dicts.
    """
    import pandas as pd

    folder = _date_folder(base_dir)
    fpath = os.path.join(folder, CURRENCY_EXPOSURE_CALC_FILE)

    try:
        if isinstance(steps, pd.DataFrame):
            df = steps
        else:
            df = pd.DataFrame(list(steps))
    except Exception as e:
        df = pd.DataFrame([{"error": f"unable to serialize steps: {e}", "repr": repr(steps)}])

    df.to_csv(fpath, index=False)



# ---------- Structured logger (console + rotating file) ----------
def get_logger(name: str = "trading_algo", level: int = logging.INFO, base_dir: str | None = None) -> logging.Logger:
    """
    Create or reuse a console + rotating-file logger.
    The file is written into today's YYYY-MM-DD folder as runtime.log.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler (rotating)
    folder = _date_folder(base_dir)
    fh = RotatingFileHandler(os.path.join(folder, "runtime.log"), maxBytes=1_000_000, backupCount=3)
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


def log_json(logger: logging.Logger, **fields) -> None:
    """Info-level JSON event."""
    logger.info(json.dumps(fields, ensure_ascii=False))


def log_exception(logger: logging.Logger, err: Exception, **context) -> None:
    """Error-level JSON event with exception message."""
    context["error"] = str(err)
    logger.error(json.dumps(context, ensure_ascii=False))
