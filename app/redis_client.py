import os
from dotenv import load_dotenv

load_dotenv()
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# decode_responses=True automatically decodes Redis bytes to Python strings
# socket_connect_timeout=0.5 ensures fast failover if Redis becomes unreachable
redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=0.5,
    socket_timeout=0.5,
)


def get_redis():
    """
    FastAPI dependency to yield the shared Redis client.
    """
    return redis_client
