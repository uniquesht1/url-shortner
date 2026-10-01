import redis
from fastapi import HTTPException, Request, status

from app.redis_client import get_redis


def rate_limit(limit: int = 30, window_seconds: int = 60):
    """
    FastAPI dependency for rate limiting per client IP using Redis.
    Defaults to 30 requests per 60 seconds.
    """
    def dependency(request: Request):
        r = get_redis()
        client_ip = request.client.host if request.client else "unknown_ip"
        path = request.url.path
        key = f"ratelimit:{client_ip}:{path}"

        try:
            current_count = r.incr(key)
            if current_count == 1:
                r.expire(key, window_seconds)

            if current_count > limit:
                ttl = r.ttl(key)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: maximum {limit} requests per {window_seconds}s. Try again in {max(1, ttl)}s.",
                    headers={"Retry-After": str(max(1, ttl))},
                )
        except HTTPException:
            raise
        except (redis.ConnectionError, redis.TimeoutError):
            # Fail-open: allow request if Redis is down
            pass

    return dependency
