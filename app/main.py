import os
from dotenv import load_dotenv

load_dotenv()

import redis
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

import app.models  # Registers URL model with Base
from app.base62 import encode
from app.bloom_filter import bloom_filter
from app.database import Base, SessionLocal, engine, get_db
from app.models import URL, ClickEvent
from app.rabbitmq_client import publish_click_event
from app.rate_limiter import rate_limit
from app.redis_client import get_redis
from app.snowflake import SnowflakeGenerator

# Automatically create tables on startup if they don't already exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="URL Shortener")

# Unique identifier for the instance (useful for load balancer tracking)
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "api")


RUN_WORKER_IN_BACKGROUND = os.getenv("RUN_WORKER_IN_BACKGROUND", "false").lower() == "true"


@app.on_event("startup")
def on_startup():
    """Populate Bloom Filter from PostgreSQL database on startup and optionally spawn worker."""
    db = SessionLocal()
    try:
        bloom_filter.populate_from_db(db)
    finally:
        db.close()

    if RUN_WORKER_IN_BACKGROUND:
        import threading
        from app.worker import start_worker

        worker_thread = threading.Thread(target=start_worker, daemon=True)
        worker_thread.start()
        print("[WORKER] Started background RabbitMQ analytics worker inside FastAPI.")


@app.middleware("http")
async def add_instance_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Handled-By"] = INSTANCE_NAME
    return response


# Initialize our Snowflake generator using env vars (default: datacenter 1, machine 1)
DATACENTER_ID = int(os.getenv("DATACENTER_ID", "1"))
MACHINE_ID = int(os.getenv("MACHINE_ID", "1"))
snowflake = SnowflakeGenerator(datacenter_id=DATACENTER_ID, machine_id=MACHINE_ID)


# Pydantic schema for incoming JSON request (validates proper URL structure)
class ShortenRequest(BaseModel):
    url: HttpUrl


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "url-shortener"}


INDEX_HTML_PATH = os.path.join(os.path.dirname(__file__), "static", "index.html")


@app.get("/", response_class=HTMLResponse)
def read_root():
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>URL Shortener</h1>")


@app.post("/shorten", dependencies=[Depends(rate_limit(limit=30, window_seconds=60))])
def shorten_url(
    payload: ShortenRequest,
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
    r: redis.Redis = Depends(get_redis),  # noqa: B008
):
    """
    1. Check Rate Limit (30 req/min per IP)
    2. Generate 64-bit Snowflake ID & Base62 short_code
    3. Save to PostgreSQL
    4. Register code in distributed Bloom filter
    5. Pre-warm Redis cache (24h TTL)
    6. Return the shortened URL
    """
    # Step 1: Generate unique Snowflake ID
    snowflake_id = snowflake.next_id()

    # Step 2: Convert ID -> Base62 short code
    short_code = encode(snowflake_id)

    # Step 3: Save to database (short_code -> original_url)
    db_url = URL(
        id=snowflake_id,
        short_code=short_code,
        original_url=str(payload.url),
    )
    db.add(db_url)
    db.commit()
    db.refresh(db_url)

    # Step 4: Add to distributed Bloom filter
    bloom_filter.add(short_code, r=r)

    # Step 5: Pre-warm Redis cache with 24 hours (86400 seconds) TTL
    try:
        r.set(f"url:{short_code}", db_url.original_url, ex=86400)
    except (redis.ConnectionError, redis.TimeoutError):
        print("[REDIS WARNING] Failed to pre-warm Redis cache on shorten.")

    # Step 6: Construct and return the full short URL
    base_url = str(request.base_url)
    short_url = f"{base_url}{short_code}"

    return {
        "short_code": short_code,
        "short_url": short_url,
        "original_url": db_url.original_url,
    }


@app.get("/{short_code}")
def redirect_to_url(
    short_code: str,
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
    r: redis.Redis = Depends(get_redis),  # noqa: B008
):
    """
    1. Emit asynchronous click event to RabbitMQ for decoupled analytics
    2. Check Redis cache (Cache-Aside pattern)
       - Cache Hit  -> 302 redirect with X-Cache: HIT
    3. Bloom Filter verification (Cache Penetration Defense)
       - If Bloom Filter returns False -> 100% Guaranteed NOT to exist -> instant 404
    4. Cache Miss -> Query PostgreSQL, populate Redis, 302 redirect with X-Cache: MISS
    5. Redis Down -> Fall back to PostgreSQL with X-Cache: BYPASS
    """
    # Step 0: Emit click analytics event to RabbitMQ (non-blocking)
    ip_addr = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    ref = request.headers.get("referer")
    publish_click_event(short_code=short_code, ip_address=ip_addr, user_agent=ua, referer=ref)

    cached_url = None
    redis_available = True

    # Attempt Redis operations safely
    try:
        r.incr(f"clicks:{short_code}")
        cached_url = r.get(f"url:{short_code}")
    except (redis.ConnectionError, redis.TimeoutError) as exc:
        redis_available = False
        print(f"[REDIS FALLBACK] Redis unavailable ({exc}). Falling back to PostgreSQL.")

    # Step 1: Cache Hit (sub-millisecond instant redirect)
    if cached_url:
        return RedirectResponse(
            url=cached_url,
            status_code=status.HTTP_302_FOUND,
            headers={"X-Cache": "HIT", "X-Bloom": "PASS"},
        )

    # Step 2: Cache Miss -> Bloom Filter Defense (Stop malicious cache penetration)
    if redis_available and not bloom_filter.contains(short_code, r=r):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short URL not found",
            headers={"X-Bloom": "REJECT"},
        )

    # Step 3: Candidate exists in Bloom Filter -> Query PostgreSQL
    db_url = db.query(URL).filter(URL.short_code == short_code).first()
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short URL not found",
        )

    # Step 4: Populate Redis cache if Redis is operational
    if redis_available:
        try:
            r.set(f"url:{short_code}", db_url.original_url, ex=86400)
        except (redis.ConnectionError, redis.TimeoutError):
            pass

    cache_header = "MISS" if redis_available else "BYPASS"
    return RedirectResponse(
        url=db_url.original_url,
        status_code=status.HTTP_302_FOUND,
        headers={"X-Cache": cache_header, "X-Bloom": "PASS"},
    )


@app.get("/stats/{short_code}")
def get_stats(
    short_code: str,
    db: Session = Depends(get_db),  # noqa: B008
    r: redis.Redis = Depends(get_redis),  # noqa: B008
):
    """
    Fetch real-time analytics: click counts from Redis and URL details.
    """
    clicks = r.get(f"clicks:{short_code}") or 0

    # Retrieve destination URL from cache or database
    cached_url = r.get(f"url:{short_code}")
    if not cached_url:
        db_url = db.query(URL).filter(URL.short_code == short_code).first()
        if not db_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Short URL not found",
            )
        target_url = db_url.original_url
    else:
        target_url = cached_url

    return {
        "short_code": short_code,
        "original_url": target_url,
        "clicks": int(clicks),
    }


@app.get("/analytics/{short_code}")
def get_analytics(
    short_code: str,
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Fetch detailed asynchronous click events collected by RabbitMQ worker.
    """
    events = (
        db.query(ClickEvent)
        .filter(ClickEvent.short_code == short_code)
        .order_by(ClickEvent.clicked_at.desc())
        .limit(50)
        .all()
    )
    return {
        "short_code": short_code,
        "total_recorded_events": len(events),
        "events": [
            {
                "id": e.id,
                "ip_address": e.ip_address,
                "user_agent": e.user_agent,
                "referer": e.referer,
                "clicked_at": e.clicked_at,
            }
            for e in events
        ],
    }



