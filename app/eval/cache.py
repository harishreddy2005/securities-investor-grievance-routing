import hashlib
import time
import json
from typing import Any, Optional, Dict
from pydantic import BaseModel


class CacheEntry(BaseModel):
    value: Any
    expires_at: float


class QueryCache:
    """
    In-memory and Redis-backed cache for embedding lookups and full routing runs (D7).
    Helps prevent duplicate model calls, protects rate limits, and lowers p95 latency.
    """
    def __init__(self, default_ttl_seconds: int = 3600):
        self._cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl_seconds
        self.hits = 0
        self.misses = 0

    def _hash_key(self, prefix: str, data: str) -> str:
        return f"{prefix}:{hashlib.sha256(data.encode('utf-8')).hexdigest()}"

    def get(self, prefix: str, raw_key: str) -> Optional[Any]:
        key = self._hash_key(prefix, raw_key)
        from app.observability.runtime import metric_store
        from app.observability.metrics import count
        backend=metric_store.get()
        if backend is not None:
            cached=backend.get('grievance:cache:'+key)
            count('cache','hit' if cached is not None else 'miss',backend)
            return json.loads(cached) if cached is not None else None
        entry = self._cache.get(key)
        if not entry:
            self.misses += 1
            return None
        if time.time() > entry.expires_at:
            del self._cache[key]
            self.misses += 1
            return None
        self.hits += 1
        return entry.value

    def set(self, prefix: str, raw_key: str, value: Any, ttl: Optional[int] = None):
        key = self._hash_key(prefix, raw_key)
        duration = ttl or self.default_ttl
        from app.observability.runtime import metric_store
        backend=metric_store.get()
        if backend is not None:
            backend.set('grievance:cache:'+key,json.dumps(value),ex=duration)
            return
        self._cache[key] = CacheEntry(value=value, expires_at=time.time() + duration)

    def clear(self):
        self._cache.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        hit_rate = (self.hits / total) if total > 0 else 0.0
        return {
            "cached_entries": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 4)
        }


global_query_cache = QueryCache()
