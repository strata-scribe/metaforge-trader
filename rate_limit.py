import time

from fastapi import HTTPException, Request


class TokenBucketRateLimiter:
    def __init__(self, requests_per_minute: int):
        self.capacity = requests_per_minute
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        # Mapping from IP address to (tokens, last_update_time)
        self.tokens: dict[str, tuple[float, float]] = {}

    async def __call__(self, request: Request):
        # We need a client IP to rate limit, fallback to "unknown" if not available
        client_ip = request.client.host if request.client else "unknown"

        current_time = time.time()

        if client_ip not in self.tokens:
            # First request, start with full capacity minus 1 (for the current request)
            self.tokens[client_ip] = (self.capacity - 1.0, current_time)
            return

        tokens, last_update = self.tokens[client_ip]

        # Calculate tokens to add based on time elapsed
        time_passed = current_time - last_update
        new_tokens = tokens + (time_passed * self.refill_rate)

        # Cap tokens at capacity
        if new_tokens > self.capacity:
            new_tokens = float(self.capacity)

        if new_tokens < 1.0:
            # Save state but deny request
            self.tokens[client_ip] = (new_tokens, current_time)
            raise HTTPException(status_code=429, detail="Too Many Requests")

        # Consume 1 token
        self.tokens[client_ip] = (new_tokens - 1.0, current_time)
