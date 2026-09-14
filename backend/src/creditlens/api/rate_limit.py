from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

_hits: dict[str, list[float]] = defaultdict(list)


def limit(request: Request, max_hits: int, window_sec: int) -> None:
    key = f"{request.client.host if request.client else 'anon'}:{request.url.path}"
    now = time.time()
    bucket = [ts for ts in _hits[key] if now - ts < window_sec]
    if len(bucket) >= max_hits:
        raise HTTPException(status_code=429, detail="Слишком много запросов")
    bucket.append(now)
    _hits[key] = bucket
