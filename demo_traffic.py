import time
import httpx

BASE_URL = "http://localhost"

def run_traffic_simulation():
    print("=" * 65)
    print(">>> GENERATING SAMPLE TRAFFIC THROUGH RABBITMQ PIPELINE <<<")
    print("=" * 65)

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        # Step 1: Create a short URL for Hacker News
        resp = client.post("/shorten", json={"url": "https://news.ycombinator.com/"})
        short_code = resp.json()["short_code"]
        print(f"\n[1] Created Short Link: http://localhost/{short_code}")
        print(f"    Target Destination: https://news.ycombinator.com/")

        # Step 2: Simulate 6 different users visiting the link from various devices and referrers
        traffic_samples = [
            {"ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1", "ref": "https://t.co/promo", "label": "iPhone 15 (Twitter/X)"},
            {"ua": "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 Chrome/122.0 Mobile Safari/537.36", "ref": "https://www.linkedin.com/feed", "label": "Samsung Galaxy (LinkedIn)"},
            {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36", "ref": "https://news.ycombinator.com", "label": "MacBook Pro (Hacker News)"},
            {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0", "ref": "https://www.google.com/search?q=url+shortener", "label": "Windows PC (Google Search)"},
            {"ua": "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1", "ref": "https://www.reddit.com/r/programming", "label": "iPad Pro (Reddit)"},
            {"ua": "curl/8.4.0", "ref": "https://github.com/my-repo", "label": "Developer CLI (GitHub)"},
        ]

        print("\n[2] Firing 6 real-world clicks through Nginx Load Balancer...")
        for i, sample in enumerate(traffic_samples, start=1):
            r = client.get(
                f"/{short_code}",
                headers={"User-Agent": sample["ua"], "Referer": sample["ref"]},
                follow_redirects=False,
            )
            handler = r.headers.get("x-handled-by")
            cache = r.headers.get("x-cache")
            print(f"    Click #{i} [{sample['label']}]: HTTP {r.status_code} Redirect -> Handled by [{handler}], X-Cache: {cache}")

        # Step 3: Wait a brief moment for worker to consume
        print("\n[3] Waiting 1.5s for RabbitMQ worker to consume queue and commit to PostgreSQL...")
        time.sleep(1.5)

        # Step 4: Fetch analytics recorded from database
        analytics_resp = client.get(f"/analytics/{short_code}")
        data = analytics_resp.json()

        print("\n[4] Querying /analytics/" + short_code + " to inspect DB records:")
        print(f"    Total Events Recorded in PostgreSQL: {data['total_recorded_events']}/6")
        print("    " + "-" * 55)
        for ev in data["events"]:
            print(f"    Event #{ev['id']}:")
            print(f"      - Device / UA: {ev['user_agent'][:50]}...")
            print(f"      - Referer:     {ev['referer']}")
            print(f"      - Timestamp:   {ev['clicked_at']}")
            print("    " + "-" * 55)

        print("\n" + "=" * 65)
        print(">>> DEMO TRAFFIC COMPLETE! CHECK RABBITMQ UI AND WORKER LOGS <<<")
        print("=" * 65)


if __name__ == "__main__":
    run_traffic_simulation()
