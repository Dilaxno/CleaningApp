"""
Service Area Validation Service

Validates ZIP codes against business-configured service areas.
Supports state, county, and neighborhood-level restrictions.
Uses zipcodes library for comprehensive US ZIP code data.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
import zipcodes
from ..models import BusinessConfig, User

logger = logging.getLogger(__name__)

# US state abbreviations to full names mapping
US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    'DC': 'District of Columbia'
}

# Reverse mapping for lookups
STATE_NAMES_TO_ABBREV = {v.lower(): k for k, v in US_STATES.items()}


class ServiceAreaValidator:
    """Validates ZIP codes against configured service areas."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_zipcode_for_business(self, zipcode: str, business_uid: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if a ZIP code is within a business's service areas.
        
        Args:
            zipcode: The ZIP code to validate (5 digits)
            business_uid: The business owner's Firebase UID
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Normalize ZIP code
            zipcode = self._normalize_zipcode(zipcode)
            if not zipcode:
                return False, "Invalid ZIP code format"
            
            # Get business config
            user = self.db.query(User).filter(User.firebase_uid == business_uid).first()
            if not user or not user.business_config:
                return False, "Business not found"
            
            service_areas = user.business_config.service_areas or []
            if not service_areas:
                # No service areas configured - allow all (backward compatibility)
                return True, None
            
            # Get ZIP code location data
            zip_location = self._get_zipcode_location(zipcode)
            if not zip_location:
                return False, "Unable to verify ZIP code location"
            
            # Check against service areas
            is_served = self._check_service_areas(zip_location, service_areas)
            
            if is_served:
                return True, None
            else:
                return False, "Sorry, but we don't serve your area yet, maybe in the future."
                
        except Exception as e:
            logger.error(f"Error validating ZIP code {zipcode} for business {business_uid}: {e}")
            return False, "Unable to verify service area"
    
    def _normalize_zipcode(self, zipcode: str) -> Optional[str]:
        """Normalize ZIP code to 5-digit format."""
        if not zipcode:
            return None
        
        # Remove all non-digits
        digits = re.sub(r'\D', '', zipcode)
        
        # Must be 5 or 9 digits (ZIP or ZIP+4)
        if len(digits) == 5:
            return digits
        elif len(digits) == 9:
            return digits[:5]  # Take first 5 digits
        else:
            return None
    
    def _get_zipcode_location(self, zipcode: str) -> Optional[Dict[str, str]]:
        """
        Get location data for a ZIP code using the zipcodes library.
        Returns standardized location information including state, county, and city.
        """
        try:
            # Use zipcodes library to lookup ZIP code
            zip_info = zipcodes.matching(zipcode)
            
            if not zip_info:
                logger.debug(f"ZIP code {zipcode} not found in database")
                return None
            
            # zipcodes.matching returns a list, get the first match
            zip_data = zip_info[0] if zip_info else None
            
            if not zip_data:
                logger.debug(f"No data found for ZIP code {zipcode}")
                return None
            
            # Extract location information
            state = zip_data.get('state')
            county = zip_data.get('county')
            city = zip_data.get('city')
            
            # Validate required fields
            if not state or not county or not city:
                logger.debug(f"ZIP code {zipcode} missing required location data: state={state}, county={county}, city={city}")
                return None
            
            # Normalize county name (ensure it ends with "County" if not already)
            if county and not county.lower().endswith('county'):
                county = f"{county} County"
            
            location_data = {
                'state': state.upper(),
                'county': county,
                'city': city,
                'zipcode': zipcode
            }
            
            logger.debug(f"ZIP code {zipcode} location: {location_data}")
            return location_data
            
        except Exception as e:
            logger.error(f"Error looking up ZIP code {zipcode}: {e}")
            return None
    
    def _check_service_areas(self, zip_location: Dict[str, str], service_areas: List[Dict]) -> bool:
        """
        Check if ZIP code location matches any configured service area.
        
        Service area types:
        - state: Serves entire state
        - county: Serves specific county within state  
        - neighborhood: Serves specific neighborhood/city within county
        """
        zip_state = zip_location.get('state', '').upper()
        zip_county = zip_location.get('county', '').lower()
        zip_city = zip_location.get('city', '').lower()
        
        for area in service_areas:
            area_type = area.get('type', '').lower()
            area_value = area.get('value', '').lower()
            area_state = area.get('state', '').upper()
            
            if area_type == 'state':
                # Check if ZIP is in this state
                if zip_state == area_state:
                    return True
                    
            elif area_type == 'county':
                # Check if ZIP is in this county and state
                if zip_state == area_state and zip_county == area_value:
                    return True
                    
            elif area_type == 'neighborhood' or area_type == 'city':
                # Check if ZIP is in this city/neighborhood, county, and state
                area_county = area.get('county', '').lower()
                if (zip_state == area_state and 
                    zip_county == area_county and 
                    zip_city == area_value):
                    return True
        
        return False
    
    def get_service_areas_for_business(self, business_uid: str) -> List[Dict]:
        """Get configured service areas for a business."""
        try:
            user = self.db.query(User).filter(User.firebase_uid == business_uid).first()
            if not user or not user.business_config:
                return []
            
            return user.business_config.service_areas or []
            
        except Exception as e:
            logger.error(f"Error getting service areas for business {business_uid}: {e}")
            return []
    
    def update_service_areas_for_business(self, business_uid: str, service_areas: List[Dict]) -> bool:
        """Update service areas for a business."""
        try:
            user = self.db.query(User).filter(User.firebase_uid == business_uid).first()
            if not user or not user.business_config:
                logger.error(f"User or business config not found for {business_uid}")
                return False
            
            # Validate service area format
            for i, area in enumerate(service_areas):
                if not self._validate_service_area_format(area):
                    logger.error(f"Invalid service area format at index {i}: {area}")
                    return False
            
            logger.info(f"Updating service areas for {business_uid}: {service_areas}")
            user.business_config.service_areas = service_areas
            self.db.commit()
            logger.info(f"Successfully updated service areas for {business_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating service areas for business {business_uid}: {e}")
            self.db.rollback()
            return False
    
    def _validate_service_area_format(self, area: Dict) -> bool:
        """Validate service area object format."""
        required_fields = ['type', 'value', 'name']
        
        # Check required fields
        for field in required_fields:
            if field not in area or not area[field]:
                return False
        
        area_type = area['type'].lower()
        
        # Valid area types
        valid_types = ['state', 'county', 'neighborhood', 'city']
        if area_type not in valid_types:
            return False
        
        # Type-specific validation
        if area_type == 'state':
            # For state type, the state code is in the 'value' field
            state_code = area.get('value', '').upper()
            return state_code in US_STATES
            
        elif area_type in ['county', 'neighborhood', 'city']:
            # County/neighborhood/city must have state field
            state_code = area.get('state', '').upper()
            if state_code not in US_STATES:
                return False
            
            # Neighborhood type must have county
            if area_type == 'neighborhood' and not area.get('county'):
                return False
        
        return True


def validate_zipcode_for_business(db: Session, zipcode: str, business_uid: str) -> Tuple[bool, Optional[str]]:
    """Convenience function for ZIP code validation."""
    validator = ServiceAreaValidator(db)
    return validator.validate_zipcode_for_business(zipcode, business_uid)