import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request

from rate_limit import TokenBucketRateLimiter


@pytest.fixture
def mock_request():
    request = MagicMock(spec=Request)
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


@pytest.mark.asyncio
async def test_token_bucket_allows_requests(mock_request):
    limiter = TokenBucketRateLimiter(requests_per_minute=60)

    # Should allow requests up to the limit
    for _ in range(60):
        await limiter(mock_request)

    # The 61st request in the exact same time should fail
    with patch("time.time", return_value=time.time()):
        with pytest.raises(HTTPException) as excinfo:
            await limiter(mock_request)
        assert excinfo.value.status_code == 429
        assert excinfo.value.detail == "Too Many Requests"


@pytest.mark.asyncio
async def test_token_bucket_refill(mock_request):
    # 60 requests per minute means 1 token per second
    limiter = TokenBucketRateLimiter(requests_per_minute=60)

    base_time = 1000.0

    # Use 60 tokens at base time
    with patch("time.time", return_value=base_time):
        for _ in range(60):
            await limiter(mock_request)

        # The 61st request should fail
        with pytest.raises(HTTPException):
            await limiter(mock_request)

    # Move forward by 0.5 seconds - not enough for 1 full token
    with patch("time.time", return_value=base_time + 0.5), pytest.raises(HTTPException):
        await limiter(mock_request)

    # Move forward by 1.1 seconds - should have 1 token
    with patch("time.time", return_value=base_time + 1.1):
        await limiter(mock_request)

        # Second request at this time should fail
        with pytest.raises(HTTPException):
            await limiter(mock_request)

    # Move forward by 60 seconds from base - should be fully refilled
    # It was at -0.1 basically, so 58.9 seconds later it adds 58.9 tokens.
    # But new_tokens > capacity will cap at 60.0.
    # At base+1.1, tokens were 0, so 58.9 seconds later we get 58.9 tokens.
    # We should move to base+65 to get 60 tokens safely.
    with patch("time.time", return_value=base_time + 65.0):
        for _ in range(60):
            await limiter(mock_request)

        with pytest.raises(HTTPException):
            await limiter(mock_request)


@pytest.mark.asyncio
async def test_token_bucket_multiple_clients():
    limiter = TokenBucketRateLimiter(requests_per_minute=10)

    request1 = MagicMock(spec=Request)
    request1.client = MagicMock()
    request1.client.host = "192.168.1.1"

    request2 = MagicMock(spec=Request)
    request2.client = MagicMock()
    request2.client.host = "192.168.1.2"

    # Client 1 uses all its tokens
    for _ in range(10):
        await limiter(request1)

    with pytest.raises(HTTPException):
        await limiter(request1)

    # Client 2 should still have its tokens
    for _ in range(10):
        await limiter(request2)

    with pytest.raises(HTTPException):
        await limiter(request2)


@pytest.mark.asyncio
async def test_token_bucket_unknown_client():
    limiter = TokenBucketRateLimiter(requests_per_minute=5)

    # Request without client
    request = MagicMock(spec=Request)
    request.client = None

    for _ in range(5):
        await limiter(request)

    with pytest.raises(HTTPException):
        await limiter(request)
