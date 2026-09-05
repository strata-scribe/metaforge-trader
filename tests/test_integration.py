import json
import os
import tempfile

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from main import DEFAULT_CONFIG, app


# Create a temporary file for config.json to isolate tests
@pytest.fixture(autouse=True)
def mock_config_file(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, 'w') as f:
        json.dump(DEFAULT_CONFIG, f)

    # Patch main.CONFIG_FILE
    monkeypatch.setattr(main, "CONFIG_FILE", path)

    # Reload config in main to reflect the new file
    main.config = main.load_config()

    yield path

    # Cleanup
    os.remove(path)

@pytest.fixture
async def async_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "deals" in data

@pytest.mark.asyncio
async def test_index_endpoint(async_client):
    # Setup some basic market state so that index.html doesn't crash if it expects fields
    main.market_state["all_listings"] = []
    main.market_state["snipes"] = []
    main.market_state["watchlist_matches"] = []
    main.market_state["priority_matches"] = []

    response = await async_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

@pytest.mark.asyncio
async def test_update_settings(async_client, mock_config_file):
    new_settings = DEFAULT_CONFIG.copy()
    new_settings["settings"]["snipe_legendary_threshold"] = 75

    response = await async_client.post("/api/settings", json=new_settings)
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    # Verify the file was updated
    with open(mock_config_file, "r") as f:
        saved_config = json.load(f)
    assert saved_config["settings"]["snipe_legendary_threshold"] == 75

    # Verify the in-memory config was updated
    assert main.config["settings"]["snipe_legendary_threshold"] == 75

@pytest.mark.asyncio
async def test_bulk_import_blueprints(async_client, mock_config_file):
    payload = {
        "type": "blueprints",
        "raw": json.dumps([{"item_id": "test-blueprint-1"}, "test-blueprint-2"])
    }
    response = await async_client.post("/api/import/bulk", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    with open(mock_config_file, "r") as f:
        saved_config = json.load(f)
    assert "test-blueprint-1" in saved_config["owned_blueprints"]
    assert "test-blueprint-2" in saved_config["owned_blueprints"]

@pytest.mark.asyncio
async def test_mark_owned(async_client, mock_config_file):
    payload = {"item_id": "test-owned-item"}
    response = await async_client.post("/api/actions/owned", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    with open(mock_config_file, "r") as f:
        saved_config = json.load(f)
    assert "test-owned-item" in saved_config["owned_blueprints"]
    assert "test-owned-item" in main.config["owned_blueprints"]

def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/ws/deals") as websocket:
        # Just sending a text to verify it stays open and can receive
        websocket.send_text("hello")
        # In main.py, the websocket endpoint just waits for text and does nothing.
        # It's an infinite loop until disconnect.
        # Check that we can send without an exception, implying it is connected.
