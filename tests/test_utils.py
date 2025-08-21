import pandas as pd

def test_round_down_to_step_and_min_lot(patch_mt5_in_sys_modules):
    from utils.utils import round_down_to_step, get_min_lot
    import MetaTrader5 as mt5

    info = mt5._Info(volume_min=0.10, volume_step=0.10)
    assert get_min_lot(info) == 0.10

    assert round_down_to_step(0.27, 0.10) == 0.20
    assert round_down_to_step(-0.27, 0.10) == -0.20
    assert round_down_to_step(0.09, 0.10) == 0.00


def test_to_usd_equivalents_basic(patch_mt5_in_sys_modules, monkeypatch):
    from utils.utils import to_usd_equivalents

    # minimal manager rows
    df = pd.DataFrame([
        {"symbol": "XAUUSD", "net_volume": 2.0, "positions": 5, "buy_volume": 1.0, "sell_volume": 3.0},
        {"symbol": "EURUSD", "net_volume": -1.0, "positions": 3, "buy_volume": 2.0, "sell_volume": 1.0},
    ])

    # price getter always returns 100 for simplicity
    def _mid(symbol):
        return 100.0

    usd_df, steps = to_usd_equivalents(df, _mid)
    # The exact USD math depends on contract sizes in your utils; here we assert passthroughs exist
    assert set(usd_df.columns) >= {"symbol", "net_volume"}
    assert len(usd_df) == 2
    assert isinstance(steps, list)
