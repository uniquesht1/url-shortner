import subprocess
import time
import httpx

BASE_URL = "http://localhost"  # Through Nginx load balancer on port 80


def test_cluster_workflow():
    print("\n" + "=" * 60)
    print("STEP 1: SEND REQUESTS THROUGH NGINX & OBSERVE LOAD BALANCING")
    print("=" * 60)

    handled_by = []
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        # Send 10 requests to root endpoint
        for i in range(10):
            r = client.get("/")
            assert r.status_code == 200
            instance = r.headers.get("x-handled-by", "unknown")
            handled_by.append(instance)

        print(f"10 requests through Nginx load balancer distribution:")
        print(f"  api1 responses: {handled_by.count('api1')}")
        print(f"  api2 responses: {handled_by.count('api2')}")
        assert "api1" in handled_by and "api2" in handled_by, "Expected traffic to be distributed across both instances!"
        print(">> LOAD BALANCER PASSED: Traffic successfully balanced across api1 and api2!")

        print("\n" + "=" * 60)
        print("STEP 2: TEST REDIS HIT / MISS THROUGH NGINX")
        print("=" * 60)

        # 1. Create short URL
        test_url = "https://www.docker.com/"
        res = client.post("/shorten", json={"url": test_url})
        assert res.status_code == 200
        data = res.json()
        short_code = data["short_code"]
        creator = res.headers.get("x-handled-by")
        print(f"Created short URL: {short_code} via [{creator}]")

        # 2. Redirect -> Expect Cache HIT (due to pre-warming)
        redirect_hit = client.get(f"/{short_code}", follow_redirects=False)
        assert redirect_hit.status_code == 302
        hit_cache = redirect_hit.headers.get("x-cache")
        handler = redirect_hit.headers.get("x-handled-by")
        print(f"First redirect: HTTP {redirect_hit.status_code}, X-Cache: {hit_cache} (Handled by {handler})")
        assert hit_cache == "HIT", f"Expected HIT, got {hit_cache}"

        # 3. Simulate Cache Miss: Evict key from Redis
        print("Evicting key from Redis to test cache miss...")
        subprocess.run(["docker", "exec", "url_shortener_redis", "redis-cli", "DEL", f"url:{short_code}"], check=True, capture_output=True)

        redirect_miss = client.get(f"/{short_code}", follow_redirects=False)
        assert redirect_miss.status_code == 302
        miss_cache = redirect_miss.headers.get("x-cache")
        handler = redirect_miss.headers.get("x-handled-by")
        print(f"Second redirect (after eviction): HTTP {redirect_miss.status_code}, X-Cache: {miss_cache} (Handled by {handler})")
        assert miss_cache == "MISS", f"Expected MISS, got {miss_cache}"
        print(">> REDIS HIT/MISS PASSED: Cache correctly bypassed and repopulated on miss!")

        print("\n" + "=" * 60)
        print("STEP 3: CHAOS TEST - KILL API #1 & VERIFY API #2 TAKES OVER")
        print("=" * 60)
        print("Stopping api1 container (docker compose stop api1)...")
        subprocess.run(["docker", "compose", "stop", "api1"], check=True, capture_output=True)

        print("Sending 6 requests through Nginx with api1 dead...")
        for i in range(6):
            r = client.get(f"/{short_code}", follow_redirects=False)
            assert r.status_code == 302
            assert r.headers.get("x-handled-by") == "api2", f"Expected api2, got {r.headers.get('x-handled-by')}"
            print(f"  Request {i + 1}: HTTP 302 -> Handled by [{r.headers.get('x-handled-by')}] (Zero Downtime!)")

        print(">> HIGH AVAILABILITY PASSED: api2 handled 100% of traffic while api1 was down!")

        # Restart api1
        print("Restarting api1 container...")
        subprocess.run(["docker", "compose", "start", "api1"], check=True, capture_output=True)
        time.sleep(2)

        print("\n" + "=" * 60)
        print("STEP 4: TEST REDIS FAILURE -> POSTGRESQL FALLBACK")
        print("=" * 60)
        print("Stopping Redis container (docker compose stop redis)...")
        subprocess.run(["docker", "compose", "stop", "redis"], check=True, capture_output=True)
        time.sleep(2)

        fallback_resp = client.get(f"/{short_code}", follow_redirects=False)
        assert fallback_resp.status_code == 302
        fallback_cache = fallback_resp.headers.get("x-cache")
        fallback_handler = fallback_resp.headers.get("x-handled-by")
        print(f"Redirect with Redis dead: HTTP {fallback_resp.status_code}, X-Cache: {fallback_cache} (Handled by {fallback_handler})")
        assert fallback_cache == "BYPASS", f"Expected BYPASS, got {fallback_cache}"
        print(">> REDIS FALLBACK PASSED: System gracefully fell back to PostgreSQL without any 500 errors!")

        # Restart redis
        print("Restarting Redis container...")
        subprocess.run(["docker", "compose", "start", "redis"], check=True, capture_output=True)

    print("\n" + "=" * 60)
    print(">>> ALL 7 SYSTEM TESTS PASSED PERFECTLY! <<<")
    print("=" * 60)


if __name__ == "__main__":
    test_cluster_workflow()
