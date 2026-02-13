"""Geocoding / Address autocomplete proxy.

Implements an OpenStreetMap Nominatim-compatible autocomplete endpoint.

Why proxy through backend?
- Avoid CORS issues in the browser
- Apply rate limits to protect upstream services
- Allow caching (Redis) to reduce load/latency

NOTE:
Nominatim usage policy requires a valid User-Agent with contact info and reasonable rate limits.
In production, consider running your own Nominatim/Photon/Pelias.
"""

import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..rate_limiter import create_rate_limiter, get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/geocoding", tags=["Geocoding"])

# Conservative default rate limit for public autocomplete
rate_limit_autocomplete = create_rate_limiter(
    limit=int(os.getenv("GEOCODING_AUTOCOMPLETE_RPM", "60")),
    window_seconds=60,
    key_prefix="geocode_autocomplete",
    use_ip=True,
)

NOMINATIM_BASE_URL = os.getenv("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org").rstrip(
    "/"
)

# Required by Nominatim policy (include a way to contact you)
NOMINATIM_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT", "CleanEnroll/1.0 (support@cleanenroll.com)"
)

CACHE_SECONDS = int(os.getenv("GEOCODING_AUTOCOMPLETE_CACHE_SECONDS", "3600"))


class AutocompleteResponseItem(BaseModel):
    display_name: str
    lat: Optional[str] = None
    lon: Optional[str] = None


class AutocompleteResponse(BaseModel):
    results: list[AutocompleteResponseItem]


@router.get("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(
    q: str,
    request: Request,
    limit: int = 6,
    countrycodes: Optional[str] = "us",
    _: None = Depends(rate_limit_autocomplete),
):
    q = (q or "").strip()
    if len(q) < 3:
        return AutocompleteResponse(results=[])

    limit = max(1, min(int(limit), 10))

    cache_key = f"geo:auto:{countrycodes or 'all'}:{limit}:{q.lower()}"

    # Try Redis cache
    try:
        redis = get_redis_client()
        cached = redis.get(cache_key)
        if cached:
            import json

            data = json.loads(cached)
            return AutocompleteResponse(results=[AutocompleteResponseItem(**x) for x in data])
    except Exception:
        # fail open
        pass

    params = {
        "q": q,
        "format": "json",
        "addressdetails": 1,
        "limit": str(limit),
        "dedupe": 1,
    }
    if countrycodes:
        params["countrycodes"] = countrycodes

    headers = {
        "User-Agent": NOMINATIM_USER_AGENT,
        "Accept": "application/json",
        "Referer": request.headers.get("Origin") or request.headers.get("Referer") or "",
    }

    url = f"{NOMINATIM_BASE_URL}/search"

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code >= 400:
                logger.warning(f"Nominatim error {resp.status_code}: {resp.text[:200]}")
                raise HTTPException(status_code=502, detail="Geocoding provider error")

            raw = resp.json()
            results = []
            for item in raw:
                dn = item.get("display_name")
                if not dn:
                    continue
                results.append(
                    {
                        "display_name": dn,
                        "lat": item.get("lat"),
                        "lon": item.get("lon"),
                    }
                )

        # Cache
        try:
            import json

            redis = get_redis_client()
            redis.setex(cache_key, CACHE_SECONDS, json.dumps(results))
        except Exception:
            pass

        return AutocompleteResponse(results=[AutocompleteResponseItem(**x) for x in results])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Autocomplete error: {e}")
        raise HTTPException(status_code=500, detail="Autocomplete failed") from e
