import hashlib

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from auth import verify_api_key

app = FastAPI()

@app.get("/secure")
async def secure_endpoint(api_key: str = Depends(verify_api_key)):
    return {"message": "Success"}

client = TestClient(app)

def test_missing_api_key():
    response = client.get("/secure")
    assert response.status_code == 401
    assert response.json() == {"detail": "Missing API Key"}

def test_invalid_api_key(monkeypatch):
    # Mock get_api_keys instead of overwriting config.json
    import auth
    monkeypatch.setattr(auth, "get_authorized_keys", lambda: ["some_hashed_key"])

    response = client.get("/secure", headers={"X-API-Key": "invalid_key"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API Key"}

def test_valid_api_key(monkeypatch):
    raw_key = "my_super_secret_key"
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

    # Mock get_api_keys instead of overwriting config.json
    import auth
    monkeypatch.setattr(auth, "get_authorized_keys", lambda: [hashed_key])

    response = client.get("/secure", headers={"X-API-Key": raw_key})
    assert response.status_code == 200
    assert response.json() == {"message": "Success"}
