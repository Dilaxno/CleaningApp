"""
Nominatim (OpenStreetMap) address autocomplete.

Free, open-source alternative to Smarty for address autocomplete.
No API keys required, just needs a user agent string.
"""

import logging
import os
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..rate_limiter import create_rate_limiter, get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/geocoding", tags=["Geocoding"])

# Rate limit for Nominatim (be respectful - max 1 request per second per their usage policy)
rate_limit_nominatim = create_rate_limiter(
    limit=int(os.getenv("NOMINATIM_AUTOCOMPLETE_RPM", "60")),  # 60 per minute = 1 per second
    window_seconds=60,
    key_prefix="nominatim_autocomplete",
    use_ip=True,
)

# Nominatim configuration
NOMINATIM_BASE_URL = os.getenv("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
NOMINATIM_USER_AGENT = os.getenv("NOMINATIM_USER_AGENT", "CleanEnroll/1.0")
CACHE_SECONDS = int(os.getenv("NOMINATIM_AUTOCOMPLETE_CACHE_SECONDS", "3600"))


class NominatimAddressSuggestion(BaseModel):
    text: str
    street_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipcode: Optional[str] = None


class NominatimAutocompleteResponse(BaseModel):
    suggestions: List[NominatimAddressSuggestion]


@router.get("/nominatim-test")
async def nominatim_test():
    """
    Test endpoint to verify Nominatim configuration.
    Returns the configuration status.
    """
    
    return {
        "nominatim_configured": True,
        "base_url": NOMINATIM_BASE_URL,
        "user_agent": NOMINATIM_USER_AGENT,
        "cache_seconds": CACHE_SECONDS,
        "rate_limit_rpm": int(os.getenv("NOMINATIM_AUTOCOMPLETE_RPM", "60")),
    }


@router.get("/nominatim-autocomplete", response_model=NominatimAutocompleteResponse)
async def nominatim_autocomplete(
    search: str,
    request: Request,
    max_results: int = 6,
    _: None = Depends(rate_limit_nominatim),
):
    """
    Nominatim address autocomplete endpoint.
    
    Args:
        search: Address search query
        max_results: Maximum number of results (1-10)
    
    Returns:
        NominatimAutocompleteResponse with address suggestions
    """
    
    search = (search or "").strip()
    if len(search) < 3:
        return NominatimAutocompleteResponse(suggestions=[])

    max_results = max(1, min(int(max_results), 10))

    # Cache key for Redis
    cache_key = f"nominatim:auto:{max_results}:{search.lower()}"

    # Try Redis cache first
    try:
        redis = get_redis_client()
        if redis:
            cached = redis.get(cache_key)
            if cached:
                import json
                data = json.loads(cached)
                return NominatimAutocompleteResponse(
                    suggestions=[NominatimAddressSuggestion(**x) for x in data]
                )
    except Exception as e:
        logger.warning(f"Redis cache read error: {e}")
        # Continue without cache

    # Prepare Nominatim API request
    params = {
        "q": search,
        "format": "json",
        "addressdetails": "1",
        "limit": str(max_results),
        "countrycodes": "us",  # Limit to US addresses
    }
    
    headers = {
        "User-Agent": NOMINATIM_USER_AGENT,
    }

    url = f"{NOMINATIM_BASE_URL}/search"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers, timeout=10.0)
            
            if resp.status_code >= 400:
                logger.warning(f"Nominatim API error {resp.status_code}: {resp.text[:200]}")
                raise HTTPException(
                    status_code=502, 
                    detail="Address lookup service temporarily unavailable"
                )

            raw_data = resp.json()
            suggestions = []
            
            # Parse Nominatim response format
            for item in raw_data:
                address = item.get("address", {})
                
                # Build street line from house number and road
                street_parts = []
                if address.get("house_number"):
                    street_parts.append(address["house_number"])
                if address.get("road"):
                    street_parts.append(address["road"])
                street_line = " ".join(street_parts) if street_parts else None
                
                # Get city (try multiple fields)
                city = (
                    address.get("city") or 
                    address.get("town") or 
                    address.get("village") or 
                    address.get("hamlet")
                )
                
                # Get state
                state = address.get("state")
                
                # Get zipcode
                zipcode = address.get("postcode")
                
                # Build display text
                display_parts = []
                if street_line:
                    display_parts.append(street_line)
                if city:
                    display_parts.append(city)
                if state:
                    display_parts.append(state)
                if zipcode:
                    display_parts.append(zipcode)
                
                text = ", ".join(display_parts) if display_parts else item.get("display_name", "")
                
                if text:
                    suggestion = NominatimAddressSuggestion(
                        text=text,
                        street_line=street_line,
                        city=city,
                        state=state,
                        zipcode=zipcode,
                    )
                    suggestions.append(suggestion)

            # Cache results
            try:
                redis = get_redis_client()
                if redis:
                    import json
                    redis.setex(
                        cache_key, 
                        CACHE_SECONDS, 
                        json.dumps([s.model_dump() for s in suggestions])
                    )
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")

        return NominatimAutocompleteResponse(suggestions=suggestions)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Nominatim autocomplete error: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Address lookup failed"
        )
