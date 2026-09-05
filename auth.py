import hashlib
import json
import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_authorized_keys():
    if not os.path.exists("config.json"):
        return []
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            return config.get("api_keys", [])
    except Exception:
        return []

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
        )

    hashed_key = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    authorized_keys = get_authorized_keys()

    if hashed_key not in authorized_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

    return api_key
