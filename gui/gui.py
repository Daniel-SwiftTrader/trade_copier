"""
Tkinter GUI (refined)
- Account panel: Balance, Equity, Margin, Profit (+ last refresh)
- Exposure (USD by Symbol) table
- Pair Net Positions table
- Trade Log (reads today's CSV) + Export
- Buttons: export CCY tables, open logs folder
"""

from __future__ import annotations

import os
import sys
import shutil
from datetime import datetime
from typing import List, Dict, Any
from config import CONFIG, SYMBOL_CONFIG

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Optional live account metrics
try:  # pragma: no cover
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None

from trade_logging.logger import export_ccy_tables_from_gui


# ---------- helpers ----------

def _today_folder() -> str:
    return os.path.join(os.getcwd(), datetime.now().strftime("%Y-%m-%d"))

def _today_trade_log_path() -> str:
    d = _today_folder()
    return os.path.join(d, f"trade_log_{datetime.now().strftime('%Y-%m-%d')}.csv")

def _fmt(x, nd=2):
    try:
        if isinstance(x, (int, float)):
            return f"{x:.{nd}f}"
        return x if x is not None else ""
    except Exception:
        return x

def _zebra_style(style: ttk.Style):
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Treeview", rowheight=24, font=("Segoe UI", 10))
    style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10))
    style.map("Treeview", background=[("selected", "#d0e7ff")])


# ---------- GUI ----------

class TradingGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Trading Dashboard")
        self.root.geometry("1400x850")

        self.style = ttk.Style(self.root)
        _zebra_style(self.style)

        self.last_usd_rows: List[Dict[str, Any]] = []
        self.last_pair_rows: List[Dict[str, Any]] = []

        # --- account strip (row 0) ---
        self._build_account_panel()
        self._build_strategy_panel()

        # --- Exposure (row 1) ---
        self.usd_columns = (
            "Symbol", "Net USD Position", "Trade Position", "Target Position",
            "Trade Delta", "Trend", "Trend Strength", "RSI", "MACD", "Reason", "PNL"
        )
        self.usd_frame, self.usd_tree = self._build_labeled_tree(
            title="Exposure (USD by Symbol)",
            columns=self.usd_columns,
            col_widths=(110, 130, 120, 120, 110, 130, 130, 80, 80, 220, 90),
        )
        self._place_section(self.usd_frame, row=2)

        # --- Pair Net Positions (row 2) ---
        self.pair_columns = ("Symbol", "Trades", "Long", "Short", "Net Position")
        self.pair_frame, self.pair_tree = self._build_labeled_tree(
            title="Pair Net Positions",
            columns=self.pair_columns,
            col_widths=(110, 90, 90, 90, 110),
        )
        self._place_section(self.pair_frame, row=3)

        # --- Trade Log (row 3) ---
        self.log_columns = ("Time", "Symbol", "Type", "Volume", "Price", "Reason")
        self.log_frame, self.log_tree = self._build_labeled_tree(
            title="Trade Log (today)",
            columns=self.log_columns,
            col_widths=(150, 90, 70, 90, 100, 400),
        )
        self._place_section(self.log_frame, row=4)

        # --- bottom controls (row 4) ---
        self._build_buttons_and_summary()

        # Grid weighting
        self.root.columnconfigure(0, weight=1)

    # ----- builders -----

    def _build_account_panel(self):
        frm = ttk.LabelFrame(self.root, text=f"Trading Account: {CONFIG['connection']['terminal_login']}")
        frm.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 2))
        for i in range(8):
            frm.columnconfigure(i, weight=1)

        self.lbl_balance = ttk.Label(frm, text="Balance: —", font=("Segoe UI", 10))
        self.lbl_equity  = ttk.Label(frm, text="Equity: —", font=("Segoe UI", 10))
        self.lbl_margin  = ttk.Label(frm, text="Margin: —", font=("Segoe UI", 10))
        self.lbl_profit  = ttk.Label(frm, text="Profit: —", font=("Segoe UI", 10))
        self.lbl_time    = ttk.Label(frm, text="Last refresh: —", anchor="e", font=("Segoe UI", 9))

        self.lbl_balance.grid(row=0, column=0, padx=8, pady=4, sticky="w")
        self.lbl_equity.grid(row=0, column=1, padx=8, pady=4, sticky="w")
        self.lbl_margin.grid(row=0, column=2, padx=8, pady=4, sticky="w")
        self.lbl_profit.grid(row=0, column=3, padx=8, pady=4, sticky="w")
        self.lbl_time.grid(row=0, column=7, padx=8, pady=4, sticky="e")

    def _build_strategy_panel(self):
        frm = ttk.LabelFrame(self.root, text=f"Manager Account: {CONFIG['connection']['manager_login']}")
        frm.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        for i in range(8):
            frm.columnconfigure(i, weight=1)
        self.lbl_follow_trade = ttk.Label(frm, text=f"Follow type: Reverse", font=("Segoe UI", 10))
        self.lbl_consolidate_usd    = ttk.Label(frm, text=f"Consolidate USD: {CONFIG['routing']['consolidate_to_usd']}", font=("Segoe UI", 10))
        self.lbl_position_multiplier  = ttk.Label(frm, text=f"Position multiplier: {CONFIG['trade_management']['trade_size_multiplier']} sec", font=("Segoe UI", 10))
        self.lbl_copy_timeframe  = ttk.Label(frm, text=f"Copy timeframe: {CONFIG['runtime']['cycle_seconds']}", font=("Segoe UI", 10))

        self.lbl_follow_trade.grid(row=0, column=0, padx=8, pady=4, sticky="w")
        self.lbl_consolidate_usd.grid(row=0, column=1, padx=8, pady=4, sticky="W")
        self.lbl_copy_timeframe.grid(row=0, column=2, padx=8, pady=4, sticky="w")
        self.lbl_position_multiplier.grid(row=0, column=3, padx=8, pady=4, sticky="w")

    def _build_labeled_tree(self, title: str, columns: tuple, col_widths: tuple):
        frame = ttk.LabelFrame(self.root, text=title)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for col, width in zip(columns, col_widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="center")

        # zebra tags
        tree.tag_configure("odd", background="#f7f7f7")
        tree.tag_configure("even", background="#ffffff")

        tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(4, 8))
        vsb.grid(row=0, column=1, sticky="ns", pady=(4, 8))
        hsb.grid(row=1, column=0, sticky="ew", padx=(10, 0))
        return frame, tree

    def _place_section(self, frame: ttk.LabelFrame, row: int):
        frame.grid(row=row, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.root.rowconfigure(row, weight=1)

    def _build_buttons_and_summary(self):
        frm = ttk.Frame(self.root)
        frm.grid(row=5, column=0, sticky="ew", padx=10, pady=(6, 10))
        frm.columnconfigure(0, weight=1)

        btns = ttk.Frame(frm)
        btns.grid(row=0, column=0, sticky="w")

        ttk.Button(btns, text="Export CCY vs USD", command=self._export_usd_pair_csvs).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Export CCY Pair", command=self._export_usd_pair_csvs).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(btns, text="Export Trade Log", command=self._export_trade_log).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(btns, text="Open Logs Folder", command=self._open_logs_folder).grid(row=0, column=3, padx=(0, 8))

        self.summary = ttk.Label(frm, text="Trades Executed: 0", anchor="w")
        self.summary.grid(row=1, column=0, sticky="ew", pady=(6, 0))

    # ----- updates -----

    def update_from_engine(self, payload: Dict[str, Any]):
        self._refresh_tree(self.usd_tree, payload.get("usd_rows", []), self.usd_columns, decimals={
            "Net USD Position": 2, "Trade Position": 2, "Target Position": 2, "Trade Delta": 2,
            "Trend Strength": 6, "RSI": 2, "MACD": 4, "PNL": 2,
        })
        self._refresh_tree(self.pair_tree, payload.get("pair_rows", []), self.pair_columns, decimals={
            "Trades": 0, "Long": 2, "Short": 2, "Net Position": 2,
        })

        self.last_usd_rows = payload.get("usd_rows", []) or []
        self.last_pair_rows = payload.get("pair_rows", []) or []

        self._refresh_trade_log()

        trades_executed = payload.get("trades_executed", 0)
        status = payload.get("status")
        suffix = f" | Status: {status}" if status else ""
        self.summary.config(text=f"Trades Executed: {trades_executed}{suffix}")
        self._update_account_metrics()
        self.lbl_time.config(text=f"Last refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def _refresh_tree(self, tree: ttk.Treeview, rows: List[Dict[str, Any]], columns: tuple, decimals: Dict[str, int]):
        for it in tree.get_children():
            tree.delete(it)
        for i, r in enumerate(rows):
            vals = []
            for col in columns:
                val = r.get(col, "")
                if col in decimals and isinstance(val, (int, float, str)):
                    try:
                        vals.append(_fmt(float(val), decimals[col]))
                    except Exception:
                        vals.append(val)
                else:
                    vals.append(val if val is not None else "")
            tag = "odd" if i % 2 else "even"
            tree.insert("", "end", values=vals, tags=(tag,))

    def _refresh_trade_log(self):
        path = _today_trade_log_path()
        for it in self.log_tree.get_children():
            self.log_tree.delete(it)
        if not os.path.exists(path):
            return
        try:
            import csv
            cols = {
                "timestamp": "Time",
                "symbol": "Symbol",
                "trade_type": "Type",
                "executed_volume": "Volume",
                "executed_price": "Price",
                "reason": "Reason",
            }
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    out = []
                    for k in cols:
                        v = row.get(k, "")
                        if k in ("executed_volume", "executed_price") and v not in ("", None):
                            try:
                                v = _fmt(float(v), 2 if k == "executed_volume" else 5)
                            except Exception:
                                pass
                        out.append(v)
                    tag = "odd" if i % 2 else "even"
                    self.log_tree.insert("", "end", values=out, tags=(tag,))
        except Exception as e:
            messagebox.showwarning("Trade Log", f"Failed to read trade log:\n{e}")

    def _update_account_metrics(self):
        if mt5 is None:
            return
        try:
            ai = mt5.account_info()
            if not ai:
                return
            self.lbl_balance.config(text=f"Balance: {_fmt(ai.balance, 2)}")
            self.lbl_equity.config(text=f"Equity: {_fmt(ai.equity, 2)}")
            self.lbl_margin.config(text=f"Margin: {_fmt(ai.margin, 2)}")
            self.lbl_profit.config(text=f"Profit: {_fmt(ai.profit, 2)}")
        except Exception:
            pass

    # ----- buttons -----

    def _export_usd_pair_csvs(self):
        export_ccy_tables_from_gui(self.last_usd_rows, self.last_pair_rows)
        messagebox.showinfo("Export", f"Exported to:\n{_today_folder()}")

    def _export_trade_log(self):
        src = _today_trade_log_path()
        if not os.path.exists(src):
            messagebox.showinfo("Export Trade Log", "No trade log found for today yet.")
            return
        dest = filedialog.asksaveasfilename(
            title="Save Trade Log As",
            defaultextension=".csv",
            initialfile=f"trade_log_{datetime.now().strftime('%Y-%m-%d')}.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not dest:
            return
        try:
            shutil.copyfile(src, dest)
            messagebox.showinfo("Export Trade Log", f"Saved:\n{dest}")
        except Exception as e:
            messagebox.showerror("Export Trade Log", f"Failed to save:\n{e}")

    def _open_logs_folder(self):
        folder = _today_folder()
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            else:
                import subprocess
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])
        except Exception as e:
            messagebox.showwarning("Open Logs Folder", f"Cannot open folder:\n{folder}\n\n{e}")


# --- simple GUI runner ---
def run_gui(engine, refresh_seconds: int | None = None):
    from config import CONFIG
    if refresh_seconds is None:
        refresh_seconds = int(CONFIG.get("runtime", {}).get("cycle_seconds", 5))

    root = tk.Tk()
    app = TradingGUI(root)

    def _tick():
        try:
            payload = engine.cycle()
            app.update_from_engine(payload)
        except Exception as e:
            root.title(f"Trading Dashboard - ERROR: {e}")
        finally:
            root.after(max(1000, int(refresh_seconds) * 1000), _tick)

    _tick()
    root.mainloop()