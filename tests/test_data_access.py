# gui/test_data_access.py


def test_manager_client_volume_net_scaling(fake_manager_table, patch_mt5_in_sys_modules):
    from data_access.data_access import ManagerClient

    # Thin wrapper matching the Manager API surface used by ManagerClient
    class FakeManager:
        def __init__(self, table):
            self._api = table
        def SummaryTotal(self):
            return len(self._api)
        def SummaryGet(self, symbol):
            return self._api.get(symbol, False)

    mc = ManagerClient()
    rows = mc.get_net_positions(FakeManager(fake_manager_table))

    xau = next(r for r in rows if r["symbol"] == "XAUUSD")
    eur = next(r for r in rows if r["symbol"] == "EURUSD")

    # VolumeNet should NOT be scaled
    assert xau["net_volume"] == 4.50
    assert eur["net_volume"] == -3.20

    # buy/sell volumes are scaled by /10000
    assert xau["buy_volume"] == 23.0
    assert xau["sell_volume"] == 8.0
    assert eur["buy_volume"] == 10.0
    assert eur["sell_volume"] == 42.0


def test_terminal_client_current_position_aggregation(patch_mt5_in_sys_modules):
    import MetaTrader5 as mt5
    from data_access.data_access import TerminalClient

    term = TerminalClient()

    # Arrange: positions in both directions
    mt5._positions.clear()
    mt5._positions.append(mt5._Position("XAUUSD", mt5.POSITION_TYPE_BUY, 1.50))
    mt5._positions.append(mt5._Position("XAUUSD", mt5.POSITION_TYPE_SELL, 0.70))
    mt5._positions.append(mt5._Position("EURUSD", mt5.POSITION_TYPE_BUY, 0.20))

    assert term.get_current_position("XAUUSD") == 0.80
    assert term.get_current_position("EURUSD") == 0.20
