import time
import httpx


def test_rabbitmq_analytics():
    print("=" * 60)
    print("TESTING ASYNCHRONOUS RABBITMQ ANALYTICS PIPELINE")
    print("=" * 60)

    base_url = "http://localhost"  # Through Nginx load balancer

    with httpx.Client(base_url=base_url) as client:
        # Step 1: Create short URL
        res = client.post("/shorten", json={"url": "https://www.rabbitmq.com/"})
        assert res.status_code == 200
        data = res.json()
        short_code = data["short_code"]
        print(f"Created short code: {short_code}")

        # Step 2: Simulate 3 clicks with distinct User-Agents
        custom_headers = [
            {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)", "Referer": "https://twitter.com"},
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://linkedin.com"},
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "Referer": "https://reddit.com"},
        ]

        print("\nSending 3 distinct clicks through Nginx...")
        for i, h in enumerate(custom_headers, start=1):
            r = client.get(f"/{short_code}", headers=h, follow_redirects=False)
            assert r.status_code == 302
            print(f"  Click {i}: Redirected to {r.headers['location']} (Handled by {r.headers.get('X-Handled-By')})")

        # Step 3: Give worker 1 second to consume and write to PostgreSQL
        print("\nWaiting 1 second for RabbitMQ background worker to process...")
        time.sleep(1)

        # Step 4: Verify analytics endpoint
        analytics_resp = client.get(f"/analytics/{short_code}")
        assert analytics_resp.status_code == 200
        analytics_data = analytics_resp.json()
        print(f"\nAnalytics API Response for '{short_code}':")
        print(f"  Total Recorded Click Events in DB: {analytics_data['total_recorded_events']}")
        for event in analytics_data["events"]:
            print(f"    - ID {event['id']}: UA='{event['user_agent'][:30]}...' Referer='{event['referer']}' at {event['clicked_at']}")

        assert analytics_data["total_recorded_events"] == 3, f"Expected 3 events, got {analytics_data['total_recorded_events']}"

        print("\n" + "=" * 60)
        print(">>> RABBITMQ ASYNCHRONOUS PIPELINE TEST PASSED! <<<")
        print("=" * 60)


if __name__ == "__main__":
    test_rabbitmq_analytics()
