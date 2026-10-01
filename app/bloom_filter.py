import hashlib
import logging

import redis
from sqlalchemy.orm import Session

from app.models import URL
from app.redis_client import get_redis

logger = logging.getLogger(__name__)


class DistributedBloomFilter:
    """
    Distributed Bloom Filter backed by Redis Bitmaps (SETBIT / GETBIT).

    Prevents Cache Penetration:
    When malicious or non-existent short codes are queried, the Bloom filter
    verifies if the key could possibly exist. If it returns False (zero false negatives),
    we immediately return 404 without querying PostgreSQL.
    """

    def __init__(self, key: str = "bloom:short_codes", size_bits: int = 1_000_000, num_hashes: int = 5):
        self.key = key
        self.size_bits = size_bits
        self.num_hashes = num_hashes

    def _get_hashes(self, item: str) -> list[int]:
        """Generate k bit indices using salted SHA-256 hashes."""
        indices = []
        for i in range(self.num_hashes):
            digest = hashlib.sha256(f"{i}:{item}".encode()).hexdigest()
            # Convert first 8 bytes of hash to integer modulo bit size
            bit_index = int(digest[:16], 16) % self.size_bits
            indices.append(bit_index)
        return indices

    def add(self, item: str, r: redis.Redis = None) -> None:
        """Add an item to the Bloom filter in Redis."""
        if r is None:
            r = get_redis()
        try:
            pipe = r.pipeline()
            for idx in self._get_hashes(item):
                pipe.setbit(self.key, idx, 1)
            pipe.execute()
        except (redis.ConnectionError, redis.TimeoutError) as exc:
            logger.warning(f"[BLOOM FILTER] Redis unavailable during add: {exc}")

    def contains(self, item: str, r: redis.Redis = None) -> bool:
        """
        Check if an item might exist in the set.
        - Returns False: 100% Guaranteed NOT to exist (0% false negatives).
        - Returns True: Probably exists (small, controlled false positive rate).
        """
        if r is None:
            r = get_redis()
        try:
            pipe = r.pipeline()
            for idx in self._get_hashes(item):
                pipe.getbit(self.key, idx)
            bits = pipe.execute()
            # If ANY bit is 0, the item definitely does NOT exist
            return all(bit == 1 for bit in bits)
        except (redis.ConnectionError, redis.TimeoutError) as exc:
            logger.warning(f"[BLOOM FILTER] Redis unavailable during check: {exc}. Allowing check to pass.")
            # Fail-open if Redis is down
            return True

    def populate_from_db(self, db: Session, r: redis.Redis = None) -> int:
        """Syncs all existing short codes from PostgreSQL into the Bloom filter on startup."""
        if r is None:
            r = get_redis()
        try:
            short_codes = [sc[0] for sc in db.query(URL.short_code).all()]
            if short_codes:
                pipe = r.pipeline()
                for sc in short_codes:
                    for idx in self._get_hashes(sc):
                        pipe.setbit(self.key, idx, 1)
                pipe.execute()
            logger.info(f"[BLOOM FILTER] Synchronized {len(short_codes)} short codes from PostgreSQL.")
            return len(short_codes)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[BLOOM FILTER] Failed to populate from DB: {exc}")
            return 0


# Shared singleton instance
bloom_filter = DistributedBloomFilter()
