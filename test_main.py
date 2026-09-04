import pytest
import asyncio
import json
import os
from main import (
    process_market_data,
    market_state,
    config,
    get_profile_slug,
    load_config,
    DEFAULT_CONFIG,
)

@pytest.fixture(autouse=True)
def reset_state():
    """Reset the global state before each test."""
    # Reset config to DEFAULT_CONFIG copy
    global config
    config.clear()
    config.update(json.loads(json.dumps(DEFAULT_CONFIG)))

    # Setup some test config defaults if needed
    config["settings"]["snipe_legendary_threshold"] = 60
    config["settings"]["snipe_epic_threshold"] = 15
    config["settings"]["max_listings_cache"] = 100
    config["ignore_list"] = ["familiar-duck"]
    config["owned_blueprints"] = []
    config["needed_items"] = {"test-item-needed": "Project: Test (Phase 1)"}
    config["watchlist"] = {"test-item-watch": 100}

    # Reset market_state
    market_state["all_listings"] = []
    market_state["snipes"] = []
    market_state["watchlist_matches"] = []
    market_state["priority_matches"] = []
    market_state["item_stats"] = {}
    market_state["stats"] = {"avg_legendary": 0, "total_volume": 0, "last_update": "Never"}

@pytest.fixture
def sample_deals():
    try:
        with open("deals.json", "r") as f:
            return json.load(f)
    except Exception:
        return []

@pytest.fixture
def base_item():
    return {
        "id": "test-uuid",
        "item_id": "test-item",
        "price": 50,
        "item": {
            "rarity": "Common"
        },
        "user_profile": {
            "username": "test_user#1234"
        }
    }

@pytest.mark.asyncio
async def test_process_market_data_empty_listings():
    """Test with zero buy orders / empty listings."""
    await process_market_data([])
    assert len(market_state["all_listings"]) == 0
    assert len(market_state["snipes"]) == 0
    assert market_state["stats"]["avg_legendary"] == 0
    assert market_state["stats"]["total_volume"] == 0
    assert market_state["item_stats"] == {}

@pytest.mark.asyncio
async def test_process_market_data_normal(base_item):
    """Test typical normal entries."""
    listing1 = base_item.copy()
    listing1["id"] = "1"
    listing1["price"] = 100
    listing1["item_id"] = "item-a"

    listing2 = base_item.copy()
    listing2["id"] = "2"
    listing2["price"] = 200
    listing2["item_id"] = "item-a"

    listing3 = base_item.copy()
    listing3["id"] = "3"
    listing3["price"] = 50
    listing3["item_id"] = "item-b"

    await process_market_data([listing1, listing2, listing3])

    assert market_state["stats"]["total_volume"] == 3
    assert len(market_state["all_listings"]) == 3

    # Check item stats (median of prices for each item)
    # item-a: median(100, 200) = 150
    # item-b: median(50) = 50
    assert market_state["item_stats"]["item-a"] == 150.0
    assert market_state["item_stats"]["item-b"] == 50.0

@pytest.mark.asyncio
async def test_process_market_data_missing_fields(base_item):
    """Test missing or malformed market entries."""
    listing_no_price = base_item.copy()
    listing_no_price["id"] = "1"
    listing_no_price["item_id"] = "item-a"
    if "price" in listing_no_price:
        del listing_no_price["price"]

    listing_no_item_id = base_item.copy()
    listing_no_item_id["id"] = "2"
    listing_no_item_id["price"] = 100
    if "item_id" in listing_no_item_id:
        del listing_no_item_id["item_id"]

    listing_no_user = base_item.copy()
    listing_no_user["id"] = "3"
    listing_no_user["price"] = 50
    listing_no_user["item_id"] = "item-b"
    if "user_profile" in listing_no_user:
        del listing_no_user["user_profile"]

    await process_market_data([listing_no_price, listing_no_item_id, listing_no_user])

    # Volume counts all inputs
    assert market_state["stats"]["total_volume"] == 3

    # But only those with both price and item_id contribute to item_stats
    assert market_state["item_stats"] == {"item-b": 50.0}

    # all_listings should have these populated correctly despite missing data
    assert len(market_state["all_listings"]) == 3
    for listing in market_state["all_listings"]:
        if listing["id"] == "3":
            assert listing["profile_slug"] == ""

@pytest.mark.asyncio
async def test_process_market_data_snipes(base_item):
    """Test epic and legendary snipes calculation."""
    legendary_snipe = base_item.copy()
    legendary_snipe["id"] = "1"
    legendary_snipe["item_id"] = "leg-item"
    legendary_snipe["item"] = {"rarity": "Legendary"}
    legendary_snipe["price"] = 50 # below 60 threshold

    epic_snipe = base_item.copy()
    epic_snipe["id"] = "2"
    epic_snipe["item_id"] = "epic-item"
    epic_snipe["item"] = {"rarity": "Epic"}
    epic_snipe["price"] = 10 # below 15 threshold

    legendary_not_snipe = base_item.copy()
    legendary_not_snipe["id"] = "3"
    legendary_not_snipe["item_id"] = "leg-item2"
    legendary_not_snipe["item"] = {"rarity": "Legendary"}
    legendary_not_snipe["price"] = 100 # above threshold

    await process_market_data([legendary_snipe, epic_snipe, legendary_not_snipe])

    assert len(market_state["snipes"]) == 2
    snipe_ids = [s["id"] for s in market_state["snipes"]]
    assert "1" in snipe_ids
    assert "2" in snipe_ids

    # average legendary price should be median of [50, 100] = 75
    assert market_state["stats"]["avg_legendary"] == 75.0

@pytest.mark.asyncio
async def test_process_market_data_ignore_and_owned(base_item):
    """Test items in ignore list or owned blueprints are skipped."""
    config["ignore_list"] = ["ignore-me"]
    config["owned_blueprints"] = ["owned-item"]

    ignored = base_item.copy()
    ignored["id"] = "1"
    ignored["item_id"] = "ignore-me"
    ignored["price"] = 10

    owned = base_item.copy()
    owned["id"] = "2"
    owned["item_id"] = "owned-item"
    owned["price"] = 20

    normal = base_item.copy()
    normal["id"] = "3"
    normal["item_id"] = "normal-item"
    normal["price"] = 30

    await process_market_data([ignored, owned, normal])

    # all_listings should not include ignored or owned
    assert len(market_state["all_listings"]) == 1
    assert market_state["all_listings"][0]["item_id"] == "normal-item"

@pytest.mark.asyncio
async def test_process_market_data_priority_and_watchlist(base_item):
    """Test needed items and watchlist matches."""
    config["needed_items"] = {"needed-item": "Quest 1"}
    config["watchlist"] = {"watch-item": 100}

    needed = base_item.copy()
    needed["id"] = "1"
    needed["item_id"] = "needed-item"
    needed["price"] = 50

    watch_match = base_item.copy()
    watch_match["id"] = "2"
    watch_match["item_id"] = "watch-item"
    watch_match["price"] = 50 # below 100

    watch_no_match = base_item.copy()
    watch_no_match["id"] = "3"
    watch_no_match["item_id"] = "watch-item"
    watch_no_match["price"] = 150 # above 100

    await process_market_data([needed, watch_match, watch_no_match])

    assert len(market_state["priority_matches"]) == 1
    assert market_state["priority_matches"][0]["id"] == "1"

    assert len(market_state["watchlist_matches"]) == 1
    assert market_state["watchlist_matches"][0]["id"] == "2"

@pytest.mark.asyncio
async def test_malformed_deals_json(sample_deals):
    """Test logic with data loaded from deals.json or similar structure, including mutated data."""
    # Run with original
    await process_market_data(sample_deals)
    original_volume = market_state["stats"]["total_volume"]

    # Let's malform some of this data
    malformed_data = []
    for item in sample_deals:
        item_copy = item.copy()
        if "item" in item_copy:
            del item_copy["item"] # missing item details (like rarity)
        if "user_profile" in item_copy:
            item_copy["user_profile"]["username"] = None # username is None
        malformed_data.append(item_copy)

    # Append a completely empty dict
    malformed_data.append({})

    # Append something with negative price to see how median logic handles it (it should just compute it)
    malformed_data.append({"item_id": "weird-item", "price": -500})

    await process_market_data(malformed_data)

    assert market_state["stats"]["total_volume"] == len(malformed_data)
    # The empty dict should not crash it
    # Median calculation of negative prices should work
    assert market_state["item_stats"].get("weird-item") == -500.0

    # Check profile slug logic for None usernames
    for listing in market_state["all_listings"]:
        if listing.get("item_id") != "weird-item": # The ones we set to None
             assert listing.get("profile_slug") == ""
