import redis
from fastapi.testclient import TestClient

from app.main import app
from app.redis_client import redis_client

client = TestClient(app)


def test_redis_cache_and_clicks():
    print("\n--- TEST: Creating a short URL ---")
    test_url = "https://www.python.org"
    response = client.post("/shorten", json={"url": test_url})
    assert response.status_code == 200, response.text
    data = response.json()
    short_code = data["short_code"]
    original_url = data["original_url"]
    print(f"Created short code: {short_code} -> {original_url}")

    # Check 1: Verify Redis pre-warming
    cached = redis_client.get(f"url:{short_code}")
    print(f"Redis cache check for 'url:{short_code}': {cached}")
    assert cached == original_url, f"Expected {original_url}, got {cached}"

    # Check 2: Call redirect endpoint (Cache HIT)
    print("\n--- TEST: Cache HIT verification ---")
    redirect_resp = client.get(f"/{short_code}", follow_redirects=False)
    assert redirect_resp.status_code == 302
    assert redirect_resp.headers["location"] == original_url
    assert redirect_resp.headers["x-cache"] == "HIT"
    print(f"Verified X-Cache header: {redirect_resp.headers['x-cache']}")

    # Check 3: Cache MISS verification (delete key from Redis, then fetch)
    print("\n--- TEST: Cache MISS verification (PostgreSQL lookup) ---")
    redis_client.delete(f"url:{short_code}")  # simulate cache eviction
    assert redis_client.get(f"url:{short_code}") is None

    miss_resp = client.get(f"/{short_code}", follow_redirects=False)
    assert miss_resp.status_code == 302
    assert miss_resp.headers["location"] == original_url
    assert miss_resp.headers["x-cache"] == "MISS"
    print(f"Verified X-Cache header on miss: {miss_resp.headers['x-cache']}")

    # Ensure Redis was repopulated after the miss
    re_cached = redis_client.get(f"url:{short_code}")
    assert re_cached == original_url
    print("Redis cache successfully repopulated from PostgreSQL!")

    # Check 4: Redis failure / fallback simulation
    print("\n--- TEST: Redis failure -> PostgreSQL fallback verification ---")
    class BrokenRedis:
        def incr(self, *args, **kwargs):
            raise redis.ConnectionError("Simulated Redis failure")
        def get(self, *args, **kwargs):
            raise redis.ConnectionError("Simulated Redis failure")
        def set(self, *args, **kwargs):
            raise redis.ConnectionError("Simulated Redis failure")

    from app.redis_client import get_redis
    app.dependency_overrides[get_redis] = lambda: BrokenRedis()

    fallback_resp = client.get(f"/{short_code}", follow_redirects=False)
    assert fallback_resp.status_code == 302
    assert fallback_resp.headers["location"] == original_url
    assert fallback_resp.headers["x-cache"] == "BYPASS"
    print(f"Fallback verified! App gracefully redirected with X-Cache: {fallback_resp.headers['x-cache']}")

    # Clear dependency override
    app.dependency_overrides.clear()

    # Check 5: Verify click counter & stats endpoint
    stats_resp = client.get(f"/stats/{short_code}")
    assert stats_resp.status_code == 200
    stats_data = stats_resp.json()
    print(f"Stats API response: {stats_data}")
    assert stats_data["original_url"] == original_url

    print("\n>>> ALL REDIS HIT/MISS & FALLBACK TESTS PASSED! <<<")


if __name__ == "__main__":
    test_redis_cache_and_clicks()
