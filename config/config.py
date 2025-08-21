CONFIG = {
    # --- Connection Settings ---
    "connection": {
        "manager_login": "5053",
        "manager_password": "4dV!KxOe",
        "manager_server": "93.118.41.10:443",
        "manager_group": "*",
        "terminal_login": "1000003",
        "terminal_password": "KeDu-n5b",
        "terminal_server": "SwiftTrader-Server",
        #"terminal_path": "123"
    },
    # --- Runtime / pacing ---
    "runtime": {
        "cycle_seconds": 120,         # GUI refresh + headless sleep between cycles
        "manager_wait_seconds": 3,   # pause after Manager.Connect() before reading
    },
    
    # --- Trade Management ---
    "trade_management": {
        # Execution & positioning parameters
        "min_positions_per_symbol": 3,
        "max_position_size": 300,           # Max absolute position (lots) per symbol
        "base_trade_volume": 0.01,          # Fallback base volume (lots)

        # Net-exposure-driven sizing (no ATR). If `use_fixed_multiplier` is True,
        # the system falls back to `fixed_multiplier` instead.
        "use_fixed_multiplier": False,
        "fixed_multiplier": 0.10,           # Kept for legacy/fallback, typically unused
        "trade_size_multiplier": 1,      # << required: latest setting

        # Position management vs. trend filters
        "close_on_neutral_trend": False,
        "close_on_opposite_trend": False,
        "allow_trades_on_neutral_trend": True,
        "allow_trades_on_opposite_trend": True,
    },

    # --- Risk Management ---
    # Keep only account-level limits here. Per-trade/SL logic will be handled in
    # trade logic without ATR inputs.
    "risk_management": {
        "daily_loss_limit": -5000.0,  # Daily loss limit in account currency
        "max_loss_per_trade": 2000.0, # Safety cap used by margin/risk guards
        "auto_close_on_daily_loss_limit": False,
    },

    # --- Indicator Settings (trend filters only) ---
    "indicators": {
        # Moving averages for directional bias
        "short_sma_period": 10,
        "long_sma_period": 50,
        "trend_strength_threshold": 0.0003,
        "neutral_trend_threshold": 0.0001,
        # RSI
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        # MACD
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
    },

    # --- Limit Order Settings (no ATR offsets) ---
    "limit_orders": {
        "use_limit_orders": False,          # True to use LIMITs instead of market
        "enable_partial_limit": True,       # Split between market/limit when enabled
        "market_order_percentage": 0.8,     # Portion filled via market when partial
        "limit_offset_points": 10,          # Fixed offset in points (no ATR)
    },
        
    # --- Files / Outputs ---
    "outputs": {
        "csv_dir_by_date": True
    },
    
    "routing": {
        # Convert non-USD crosses (e.g., EURJPY) into USD legs to match currency exposures
        "consolidate_to_usd": True,  # set False to keep trading original pairs
        # Only these USD pairs are eligible to trade (adjust to your broker’s symbols)
        "usd_pairs": ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD", "XAUUSD", "XAGUSD"],
        # If a symbol is already a USD cross and allowed, use it as-is
        "use_original_for_usd_pairs": True,
        # Drop synthetic legs that round below min lot
        "skip_below_min": True,
    },
}