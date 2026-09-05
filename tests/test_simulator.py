import pytest
from simulator import SimulatedTradingEngine

def test_initialization():
    engine = SimulatedTradingEngine(1000.0)
    assert engine.balance == 1000.0
    assert engine.initial_balance == 1000.0
    assert len(engine.portfolio) == 0
    assert len(engine.active_orders) == 0

def test_submit_order():
    engine = SimulatedTradingEngine()

    order_id = engine.submit_order("buy", "item_1", 2, 50.0)
    assert order_id == 1
    assert len(engine.active_orders) == 1

    order = engine.active_orders[0]
    assert order["side"] == "buy"
    assert order["item_id"] == "item_1"
    assert order["quantity"] == 2
    assert order["limit_price"] == 50.0
    assert order["filled"] == 0

def test_invalid_orders():
    engine = SimulatedTradingEngine()
    with pytest.raises(ValueError):
        engine.submit_order("invalid_side", "item_1", 1, 10.0)

    with pytest.raises(ValueError):
        engine.submit_order("buy", "item_1", 0, 10.0)

    with pytest.raises(ValueError):
        engine.submit_order("sell", "item_1", 1, 0)

def test_match_buy_order():
    engine = SimulatedTradingEngine(1000.0)
    engine.submit_order("buy", "item_1", 2, 50.0)

    # Matching listings
    listings = [
        {"item_id": "item_1", "price": 40.0, "quantity": 1},
        {"item_id": "item_1", "price": 45.0, "quantity": 1},
        {"item_id": "item_1", "price": 55.0, "quantity": 1} # Too expensive
    ]

    engine.match_against_listings(listings)

    assert engine.balance == 1000.0 - 40.0 - 45.0
    assert engine.portfolio["item_1"] == 2
    assert len(engine.active_orders) == 0 # Fully filled

def test_match_sell_order():
    engine = SimulatedTradingEngine(1000.0)
    # Give some portfolio balance first
    engine.portfolio["item_2"] = 3

    engine.submit_order("sell", "item_2", 2, 100.0)

    # Need market listings for item_2 >= 100.0 to trigger sell
    listings = [
        {"item_id": "item_2", "price": 105.0, "quantity": 1}
    ]

    engine.match_against_listings(listings)

    # Sold 2 at 100.0
    assert engine.balance == 1000.0 + 200.0
    assert engine.portfolio["item_2"] == 1
    assert len(engine.active_orders) == 0

def test_pnl_calculation():
    engine = SimulatedTradingEngine(1000.0)
    engine.portfolio["item_3"] = 2
    engine.balance = 1200.0 # Realized 200 profit somehow

    market_prices = {
        "item_3": 150.0
    }

    pnl = engine.get_pnl(market_prices)

    assert pnl["realized_pnl"] == 200.0
    assert pnl["unrealized_pnl"] == 300.0 # 2 * 150
    assert pnl["total_pnl"] == 500.0
    assert pnl["portfolio_value"] == 300.0
    assert pnl["cash_balance"] == 1200.0
