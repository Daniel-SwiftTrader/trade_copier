import os
from datetime import datetime

def test_csv_writers(tmp_path):
    from trade_logging.logger import (
        log_trade_csv, log_rejected_csv, log_account_metrics_csv, write_daily_summary_csv, write_exposure_tables
    )
    import pandas as pd

    base = tmp_path
    # Trades
    log_trade_csv({"symbol": "XAUUSD", "trade_type": "BUY", "requested_volume": 0.2}, base_dir=base)
    # Rejected
    log_rejected_csv({"symbol": "EURUSD", "reason": "Delta too small"}, base_dir=base)
    # Metrics
    log_account_metrics_csv({"balance": 100000, "equity": 100000}, base_dir=base)
    # Summary
    write_daily_summary_csv({"date": "2099-01-01", "total_trades": 3}, base_dir=base)
    # Exposure tables
    usd_df = pd.DataFrame([{"symbol": "XAUUSD", "net_volume": 1.0}])
    write_exposure_tables(usd_df, str(base))

    # Verify files exist in date folder
    date_folder = os.path.join(str(base), datetime.now().strftime("%Y-%m-%d"))
    assert os.path.isdir(date_folder)
    assert any(f.startswith("trade_log_") for f in os.listdir(date_folder))
    assert any(f.startswith("rejected_trade_log_") for f in os.listdir(date_folder))
    assert any(f.startswith("account_metrics_") for f in os.listdir(date_folder))
    assert any(f.startswith("daily_summary_") for f in os.listdir(date_folder))
    assert "exposure_net_positions.csv" in os.listdir(date_folder)
    assert "previous_net_positions.csv" in os.listdir(date_folder)
