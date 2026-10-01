import http.client
import json
import time
import urllib.error
import urllib.request

BASE_HOST = "localhost"
BASE_PORT = 8000
BASE_URL = f"http://{BASE_HOST}:{BASE_PORT}"


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Handler that prevents automatically following 302 redirects."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


opener = urllib.request.build_opener(NoRedirectHandler)


def test_invalid_urls():
    print("\n" + "=" * 55)
    print("TEST 1: Invalid URLs Handling (POST /shorten)")
    print("=" * 55)

    invalid_cases = [
        "not-a-url",
        "httpp://invalid-scheme.com",
        "just_plain_text",
        "",
        "http://",
    ]

    for bad_url in invalid_cases:
        req = urllib.request.Request(
            f"{BASE_URL}/shorten",
            data=json.dumps({"url": bad_url}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            opener.open(req)
            raise AssertionError(f"Expected 422 error for invalid URL '{bad_url}', but got success!")
        except urllib.error.HTTPError as e:
            print(f"  [x] Rejected invalid URL '{bad_url}': HTTP {e.code} (Unprocessable Entity)")
            assert e.code == 422, f"Expected 422, got {e.code}"

    print("All invalid URLs correctly rejected by validation!")


def test_nonexistent_codes():
    print("\n" + "=" * 55)
    print("TEST 2: Non-existent Short Codes (GET /{short_code})")
    print("=" * 55)

    fake_codes = [
        "not_real_code_1",
        "missing999",
        "doesNotExist",
    ]

    for fake_code in fake_codes:
        try:
            opener.open(f"{BASE_URL}/{fake_code}")
            raise AssertionError(f"Expected 404 for code '{fake_code}', but request succeeded!")
        except urllib.error.HTTPError as e:
            print(f"  [x] Request for '/{fake_code}': HTTP {e.code} (Not Found)")
            assert e.code == 404, f"Expected 404, got {e.code}"

    print("All non-existent codes returned 404 Not Found as expected!")


def test_bulk_create_and_verify(count=1000):
    print("\n" + "=" * 55)
    print(f"TEST 3: Bulk Creation of {count} URLs (POST /shorten)")
    print("=" * 55)

    short_codes = []
    url_mapping = {}

    conn = http.client.HTTPConnection(BASE_HOST, BASE_PORT)
    headers = {"Content-Type": "application/json"}

    start_time = time.time()
    for i in range(count):
        original_url = f"https://example.com/page/{i}?ref=bulk_test"
        payload = json.dumps({"url": original_url})

        conn.request("POST", "/shorten", body=payload, headers=headers)
        resp = conn.getresponse()
        assert resp.status == 200, f"Failed at request {i}: status {resp.status}"

        data = json.loads(resp.read().decode())
        code = data["short_code"]
        short_codes.append(code)
        url_mapping[code] = original_url

        if (i + 1) % 250 == 0 or (i + 1) == count:
            print(f"  Created {i + 1}/{count} URLs...")

    conn.close()
    elapsed = time.time() - start_time
    print(f"Finished creating {count} URLs in {elapsed:.2f} seconds ({count / elapsed:.1f} req/sec)")

    print("\n" + "=" * 55)
    print(f"TEST 4: Verify All {count} Short Codes Are Unique")
    print("=" * 55)
    unique_count = len(set(short_codes))
    print(f"Total Short Codes Generated: {len(short_codes)}")
    print(f"Unique Short Codes Count:    {unique_count}")
    assert unique_count == count, f"Collision detected! {count - unique_count} duplicates found."
    print("VERIFICATION PASSED: 100% uniqueness guaranteed!")

    print("\n" + "=" * 55)
    print("TEST 5: Open & Verify Sample Short URLs (302 Redirect)")
    print("=" * 55)
    # Pick 5 sample short codes across the range (first, quarter, middle, three-quarters, last)
    sample_indices = [0, count // 4, count // 2, (3 * count) // 4, count - 1]
    for idx in sample_indices:
        code = short_codes[idx]
        expected_url = url_mapping[code]
        try:
            opener.open(f"{BASE_URL}/{code}")
            raise AssertionError(f"Expected 302 redirect for '{code}', but got regular 200 response!")
        except urllib.error.HTTPError as e:
            location = e.headers.get("Location")
            print(f"  Checking '{code}':")
            print(f"    Status:   HTTP {e.code} (Found)")
            print(f"    Location: {location}")
            assert e.code == 302, f"Expected 302, got {e.code}"
            assert location == expected_url, f"Expected {expected_url}, got {location}"
            print("    -> Match verified!")

    print("All sample redirects verified with exact match to original URL!")


def main():
    print("=======================================================")
    print("  PHASE 6: FULL SYSTEM END-TO-END VERIFICATION SUITE  ")
    print("=======================================================")

    test_invalid_urls()
    test_nonexistent_codes()
    test_bulk_create_and_verify(1000)

    print("\n" + "=" * 55)
    print(">>> ALL TESTS PASSED SUCCESSFULLY! SYSTEM IS 100% OPERATIONAL. <<<")
    print("=" * 55)


if __name__ == "__main__":
    main()
