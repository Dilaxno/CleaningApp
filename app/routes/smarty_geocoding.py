"""
Smarty address autocomplete proxy.

Implements address autocomplete using Smarty's US Street API.
Provides secure API key handling and caching for better performance.
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

# Rate limit for Smarty autocomplete
rate_limit_smarty = create_rate_limiter(
    limit=int(os.getenv("SMARTY_AUTOCOMPLETE_RPM", "100")),
    window_seconds=60,
    key_prefix="smarty_autocomplete",
    use_ip=True,
)

# Smarty configuration
SMARTY_AUTH_ID = os.getenv("SMARTY_AUTH_ID")
SMARTY_AUTH_TOKEN = os.getenv("SMARTY_AUTH_TOKEN")
SMARTY_BASE_URL = "https://us-autocomplete-pro.api.smarty.com"

CACHE_SECONDS = int(os.getenv("SMARTY_AUTOCOMPLETE_CACHE_SECONDS", "3600"))


class SmartyAddressSuggestion(BaseModel):
    text: str
    street_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipcode: Optional[str] = None


class SmartyAutocompleteResponse(BaseModel):
    suggestions: List[SmartyAddressSuggestion]


@router.get("/smarty-test")
async def smarty_test():
    """
    Test endpoint to verify Smarty API configuration.
    Returns the configuration status without exposing sensitive data.
    """
    
    has_auth_id = bool(SMARTY_AUTH_ID)
    has_auth_token = bool(SMARTY_AUTH_TOKEN)
    
    return {
        "smarty_configured": has_auth_id and has_auth_token,
        "auth_id_present": has_auth_id,
        "auth_token_present": has_auth_token,
        "base_url": SMARTY_BASE_URL,
        "cache_seconds": CACHE_SECONDS,
    }


@router.get("/smarty-autocomplete", response_model=SmartyAutocompleteResponse)
async def smarty_autocomplete(
    search: str,
    request: Request,
    max_results: int = 6,
    _: None = Depends(rate_limit_smarty),
):
    """
    Smarty address autocomplete endpoint.
    
    Args:
        search: The address search query
        max_results: Maximum number of results to return (1-10)
    
    Returns:
        SmartyAutocompleteResponse with address suggestions
    """
    
    # Validate API credentials
    if not SMARTY_AUTH_ID or not SMARTY_AUTH_TOKEN:
        logger.error("Smarty API credentials not configured")
        raise HTTPException(
            status_code=500, 
            detail="Address autocomplete service not configured"
        )
    
    search = (search or "").strip()
    if len(search) < 3:
        return SmartyAutocompleteResponse(suggestions=[])

    max_results = max(1, min(int(max_results), 10))

    # Cache key for Redis
    cache_key = f"smarty:auto:{max_results}:{search.lower()}"

    # Try Redis cache first
    try:
        redis = get_redis_client()
        cached = redis.get(cache_key)
        if cached:
            import json
            data = json.loads(cached)
            return SmartyAutocompleteResponse(
                suggestions=[SmartyAddressSuggestion(**x) for x in data]
            )
    except Exception as e:
        logger.warning(f"Redis cache error: {e}")
        # Continue without cache

    # Prepare Smarty API request
    params = {
        "auth-id": SMARTY_AUTH_ID,
        "auth-token": SMARTY_AUTH_TOKEN,
        "search": search,
        "max_results": str(max_results),
        "include_only_cities": [],  # Include all types
        "include_only_states": [],  # Include all states
    }

    headers = {
        "Accept": "application/json",
        "User-Agent": "CleanEnroll/1.0",
        "Referer": request.headers.get("Origin") or request.headers.get("Referer") or "",
    }

    url = f"{SMARTY_BASE_URL}/lookup"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            
            if resp.status_code == 401:
                logger.error("Smarty API authentication failed")
                raise HTTPException(
                    status_code=500, 
                    detail="Address service authentication failed"
                )
            elif resp.status_code == 402:
                logger.error("Smarty API payment required")
                raise HTTPException(
                    status_code=500, 
                    detail="Address service quota exceeded"
                )
            elif resp.status_code >= 400:
                logger.warning(f"Smarty API error {resp.status_code}: {resp.text[:200]}")
                raise HTTPException(
                    status_code=502, 
                    detail="Address service temporarily unavailable"
                )

            raw_data = resp.json()
            suggestions = []
            
            # Parse Smarty response format
            for item in raw_data.get("suggestions", []):
                suggestion = SmartyAddressSuggestion(
                    text=item.get("text", ""),
                    street_line=item.get("street_line"),
                    city=item.get("city"),
                    state=item.get("state"),
                    zipcode=item.get("zipcode"),
                )
                if suggestion.text:
                    suggestions.append(suggestion)

        # Cache successful results
        try:
            import json
            redis = get_redis_client()
            cache_data = [s.dict() for s in suggestions]
            redis.setex(cache_key, CACHE_SECONDS, json.dumps(cache_data))
        except Exception as e:
            logger.warning(f"Redis cache write error: {e}")

        return SmartyAutocompleteResponse(suggestions=suggestions)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Smarty autocomplete error: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Address autocomplete service error"
        )