import time
import httpx

BASE_URL = "http://localhost"  # Through Nginx load balancer


def test_bloom_filter_defense(client: httpx.Client):
    print("\n" + "=" * 60)
    print("TEST 1: BLOOM FILTER CACHE PENETRATION DEFENSE")
    print("=" * 60)

    # 1. Non-existent random short codes should be rejected by the Bloom filter immediately
    bogus_codes = ["fakeCode123", "nonExistent999", "ghostLinkXYZ"]
    for code in bogus_codes:
        resp = client.get(f"/{code}", follow_redirects=False)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        bloom_header = resp.headers.get("x-bloom")
        print(f"  Querying non-existent '/{code}' -> HTTP 404, X-Bloom: {bloom_header}")
        assert bloom_header == "REJECT", f"Expected X-Bloom: REJECT, got {bloom_header}"

    print(">> PASSED: Bloom filter rejected malicious non-existent queries without querying PostgreSQL!")

    # 2. Existing short code should pass Bloom filter
    res = client.post("/shorten", json={"url": "https://en.wikipedia.org/wiki/Bloom_filter"})
    assert res.status_code == 200
    valid_code = res.json()["short_code"]
    print(f"\n  Created real code: '{valid_code}'")

    valid_resp = client.get(f"/{valid_code}", follow_redirects=False)
    assert valid_resp.status_code == 302
    assert valid_resp.headers.get("x-bloom") == "PASS"
    print(f"  Querying valid '/{valid_code}' -> HTTP 302, X-Bloom: {valid_resp.headers.get('x-bloom')}")
    print(">> PASSED: Real short code successfully passed Bloom filter!")


def test_rate_limiting(client: httpx.Client):
    print("\n" + "=" * 60)
    print("TEST 2: REDIS-BASED RATE LIMITING")
    print("=" * 60)

    # Limit on /shorten is 30 requests per minute
    print("Sending 35 rapid /shorten requests to trigger 429 Too Many Requests...")
    exceeded = False
    for i in range(1, 36):
        resp = client.post("/shorten", json={"url": f"https://example.com/item/{i}"})
        if resp.status_code == 429:
            exceeded = True
            retry_after = resp.headers.get("retry-after")
            print(f"  Request #{i}: HTTP 429 Too Many Requests! Retry-After: {retry_after}s")
            print(f"  Response detail: {resp.json().get('detail')}")
            break

    assert exceeded, "Rate limit was not triggered after 35 rapid requests!"
    print(">> PASSED: Rate limiter successfully blocked abuse with HTTP 429!")

    # Clean up rate limit key so other tests are not blocked
    import subprocess
    subprocess.run(["docker", "exec", "url_shortener_redis", "redis-cli", "DEL", "ratelimit:172.20.0.7:/shorten"], capture_output=True)


def main():
    print("============================================================")
    print("     PHASE 8: OPTIMIZATIONS VERIFICATION SUITE              ")
    print("============================================================")

    import subprocess
    # Clean up any leftover rate limit keys from previous runs
    subprocess.run(["docker", "exec", "url_shortener_redis", "redis-cli", "DEL", "ratelimit:172.20.0.7:/shorten"], capture_output=True)

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        test_bloom_filter_defense(client)
        test_rate_limiting(client)

    print("\n" + "=" * 60)
    print(">>> ALL PHASE 8 OPTIMIZATION TESTS PASSED! <<<")
    print("=" * 60)


if __name__ == "__main__":
    main()
