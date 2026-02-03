"""
Service Area Validation Service

Validates client ZIP codes against business owner's configured service areas.
Supports multiple validation types: radius-based, ZIP code lists, state/county restrictions.
"""

import logging
import math
import re
from typing import Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from ..models import BusinessConfig

logger = logging.getLogger(__name__)


class ServiceAreaValidator:
    """Validates client locations against business service areas."""

    def __init__(self, db: Session):
        self.db = db

    async def validate_zipcode(
        self, business_config: BusinessConfig, zipcode: str
    ) -> Dict[str, any]:
        """
        Validate a ZIP code against the business's service area configuration.
        
        Args:
            business_config: BusinessConfig object with service area settings
            zipcode: Client's ZIP code to validate
            
        Returns:
            Dict with validation result:
            {
                "allowed": bool,
                "reason": str,
                "zipcode_info": dict (if available)
            }
        """
        # Clean and validate ZIP code format
        clean_zipcode = self._clean_zipcode(zipcode)
        if not clean_zipcode:
            return {
                "allowed": False,
                "reason": "Invalid ZIP code format",
                "zipcode_info": None
            }

        # If service area is not enabled, allow all
        if not business_config.service_area_enabled:
            return {
                "allowed": True,
                "reason": "Service area restrictions not enabled",
                "zipcode_info": None
            }

        # Get ZIP code geographic information
        zipcode_info = await self._get_zipcode_info(clean_zipcode)
        if not zipcode_info:
            return {
                "allowed": False,
                "reason": "Unable to verify ZIP code location",
                "zipcode_info": None
            }

        # Validate based on service area type
        service_area_type = business_config.service_area_type

        if service_area_type == "zipcode":
            return self._validate_zipcode_list(business_config, clean_zipcode, zipcode_info)
        elif service_area_type == "radius":
            return self._validate_radius(business_config, zipcode_info)
        elif service_area_type == "custom":
            return self._validate_custom_areas(business_config, clean_zipcode, zipcode_info)
        else:
            return {
                "allowed": False,
                "reason": "Service area type not configured",
                "zipcode_info": zipcode_info
            }

    def _clean_zipcode(self, zipcode: str) -> Optional[str]:
        """Clean and validate ZIP code format."""
        if not zipcode:
            return None
        
        # Remove all non-digit characters
        clean = re.sub(r'\D', '', zipcode.strip())
        
        # US ZIP codes are 5 or 9 digits
        if len(clean) == 5 or len(clean) == 9:
            return clean[:5]  # Return 5-digit ZIP
        
        return None

    async def _get_zipcode_info(self, zipcode: str) -> Optional[Dict]:
        """
        Get geographic information for a ZIP code using a geocoding service.
        Returns lat/lon, city, state, county information.
        """
        try:
            # Use a free ZIP code API (you can replace with your preferred service)
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Using zippopotam.us - free ZIP code API
                response = await client.get(f"http://api.zippopotam.us/us/{zipcode}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("places"):
                        place = data["places"][0]
                        return {
                            "zipcode": zipcode,
                            "city": place.get("place name"),
                            "state": place.get("state abbreviation"),
                            "state_full": place.get("state"),
                            "county": place.get("county", "").replace(" County", ""),
                            "latitude": float(place.get("latitude", 0)),
                            "longitude": float(place.get("longitude", 0))
                        }
        except Exception as e:
            logger.warning(f"Failed to get ZIP code info for {zipcode}: {e}")
        
        return None

    def _validate_zipcode_list(
        self, business_config: BusinessConfig, zipcode: str, zipcode_info: Dict
    ) -> Dict[str, any]:
        """Validate against explicit ZIP code list."""
        allowed_zipcodes = business_config.service_area_zipcodes or []
        
        if zipcode in allowed_zipcodes:
            return {
                "allowed": True,
                "reason": "ZIP code in allowed list",
                "zipcode_info": zipcode_info
            }
        
        # Also check state/county restrictions if configured
        state_county_result = self._check_state_county_restrictions(
            business_config, zipcode_info
        )
        
        if state_county_result["allowed"]:
            return state_county_result
        
        return {
            "allowed": False,
            "reason": "ZIP code not in service area",
            "zipcode_info": zipcode_info
        }

    def _validate_radius(
        self, business_config: BusinessConfig, zipcode_info: Dict
    ) -> Dict[str, any]:
        """Validate against radius-based service area."""
        center_lat = business_config.service_area_center_lat
        center_lon = business_config.service_area_center_lon
        radius_miles = business_config.service_area_radius_miles
        
        if not all([center_lat, center_lon, radius_miles]):
            return {
                "allowed": False,
                "reason": "Radius service area not properly configured",
                "zipcode_info": zipcode_info
            }
        
        zip_lat = zipcode_info.get("latitude")
        zip_lon = zipcode_info.get("longitude")
        
        if not zip_lat or not zip_lon:
            return {
                "allowed": False,
                "reason": "Unable to determine ZIP code coordinates",
                "zipcode_info": zipcode_info
            }
        
        distance = self._calculate_distance(center_lat, center_lon, zip_lat, zip_lon)
        
        if distance <= radius_miles:
            return {
                "allowed": True,
                "reason": f"Within {radius_miles} mile service radius ({distance:.1f} miles)",
                "zipcode_info": zipcode_info
            }
        
        return {
            "allowed": False,
            "reason": f"Outside {radius_miles} mile service radius ({distance:.1f} miles)",
            "zipcode_info": zipcode_info
        }

    def _validate_custom_areas(
        self, business_config: BusinessConfig, zipcode: str, zipcode_info: Dict
    ) -> Dict[str, any]:
        """Validate against custom area definitions (states, counties, neighborhoods)."""
        # Check explicit ZIP codes first
        allowed_zipcodes = business_config.service_area_zipcodes or []
        if zipcode in allowed_zipcodes:
            return {
                "allowed": True,
                "reason": "ZIP code in allowed list",
                "zipcode_info": zipcode_info
            }
        
        # Check state/county restrictions
        return self._check_state_county_restrictions(business_config, zipcode_info)

    def _check_state_county_restrictions(
        self, business_config: BusinessConfig, zipcode_info: Dict
    ) -> Dict[str, any]:
        """Check state and county restrictions."""
        state = zipcode_info.get("state")
        county = zipcode_info.get("county")
        
        # Check state restrictions
        allowed_states = business_config.service_area_states or []
        if allowed_states and state not in allowed_states:
            return {
                "allowed": False,
                "reason": f"State {state} not in service area",
                "zipcode_info": zipcode_info
            }
        
        # Check county restrictions
        allowed_counties = business_config.service_area_counties or []
        if allowed_counties and county:
            # Counties are stored in "STATE:COUNTY" format
            county_key = f"{state}:{county}"
            if county_key not in allowed_counties:
                return {
                    "allowed": False,
                    "reason": f"County {county}, {state} not in service area",
                    "zipcode_info": zipcode_info
                }
        
        # Check neighborhood restrictions (if implemented)
        # This would require more detailed geocoding data
        
        return {
            "allowed": True,
            "reason": "Location within configured service area",
            "zipcode_info": zipcode_info
        }

    def _calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate the great circle distance between two points on Earth.
        Returns distance in miles.
        """
        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Radius of Earth in miles
        r = 3956
        
        return c * r

    async def get_service_area_summary(self, business_config: BusinessConfig) -> Dict:
        """Get a human-readable summary of the service area configuration."""
        if not business_config.service_area_enabled:
            return {"enabled": False, "description": "Service area restrictions disabled"}
        
        service_type = business_config.service_area_type
        
        if service_type == "radius":
            radius = business_config.service_area_radius_miles
            return {
                "enabled": True,
                "type": "radius",
                "description": f"Within {radius} miles of business location"
            }
        
        elif service_type == "zipcode":
            zipcodes = business_config.service_area_zipcodes or []
            count = len(zipcodes)
            return {
                "enabled": True,
                "type": "zipcode",
                "description": f"Specific ZIP codes ({count} configured)"
            }
        
        elif service_type == "custom":
            states = business_config.service_area_states or []
            counties = business_config.service_area_counties or []
            zipcodes = business_config.service_area_zipcodes or []
            
            parts = []
            if states:
                parts.append(f"{len(states)} states")
            if counties:
                parts.append(f"{len(counties)} counties")
            if zipcodes:
                parts.append(f"{len(zipcodes)} ZIP codes")
            
            description = "Custom areas: " + ", ".join(parts) if parts else "Custom areas configured"
            
            return {
                "enabled": True,
                "type": "custom",
                "description": description
            }
        
        return {
            "enabled": True,
            "type": "unknown",
            "description": "Service area configured but type unknown"
        }