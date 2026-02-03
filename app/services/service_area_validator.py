"""
Service Area Validation Service

Validates ZIP codes against business-configured service areas.
Supports state, county, and neighborhood-level restrictions.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
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
        Get location data for a ZIP code.
        In a production system, this would use a ZIP code database or API.
        For now, we'll use a simplified approach with Smarty API if available.
        """
        # TODO: Integrate with ZIP code database or Smarty API
        # For now, return a mock structure that would come from a real service
        
        # This is a placeholder - in production you'd query:
        # 1. A ZIP code database (like USPS ZIP code files)
        # 2. Smarty Streets API with ZIP code lookup
        # 3. Census Bureau API
        # 4. Commercial ZIP code service
        
        # Mock data structure for development - covers major US cities
        mock_locations = {
            # California
            '90210': {'state': 'CA', 'county': 'Los Angeles County', 'city': 'Beverly Hills'},
            '90211': {'state': 'CA', 'county': 'Los Angeles County', 'city': 'Beverly Hills'},
            '90401': {'state': 'CA', 'county': 'Los Angeles County', 'city': 'Santa Monica'},
            '90402': {'state': 'CA', 'county': 'Los Angeles County', 'city': 'Santa Monica'},
            '94102': {'state': 'CA', 'county': 'San Francisco County', 'city': 'San Francisco'},
            '94103': {'state': 'CA', 'county': 'San Francisco County', 'city': 'San Francisco'},
            '95014': {'state': 'CA', 'county': 'Santa Clara County', 'city': 'Cupertino'},
            
            # New York
            '10001': {'state': 'NY', 'county': 'New York County', 'city': 'New York'},
            '10002': {'state': 'NY', 'county': 'New York County', 'city': 'New York'},
            '10003': {'state': 'NY', 'county': 'New York County', 'city': 'New York'},
            '10004': {'state': 'NY', 'county': 'New York County', 'city': 'New York'},
            '10005': {'state': 'NY', 'county': 'New York County', 'city': 'New York'},
            '11201': {'state': 'NY', 'county': 'Kings County', 'city': 'Brooklyn'},
            '11202': {'state': 'NY', 'county': 'Kings County', 'city': 'Brooklyn'},
            
            # Illinois
            '60601': {'state': 'IL', 'county': 'Cook County', 'city': 'Chicago'},
            '60602': {'state': 'IL', 'county': 'Cook County', 'city': 'Chicago'},
            '60603': {'state': 'IL', 'county': 'Cook County', 'city': 'Chicago'},
            '60604': {'state': 'IL', 'county': 'Cook County', 'city': 'Chicago'},
            
            # Texas
            '77001': {'state': 'TX', 'county': 'Harris County', 'city': 'Houston'},
            '77002': {'state': 'TX', 'county': 'Harris County', 'city': 'Houston'},
            '77003': {'state': 'TX', 'county': 'Harris County', 'city': 'Houston'},
            '75201': {'state': 'TX', 'county': 'Dallas County', 'city': 'Dallas'},
            '75202': {'state': 'TX', 'county': 'Dallas County', 'city': 'Dallas'},
            '78701': {'state': 'TX', 'county': 'Travis County', 'city': 'Austin'},
            '78702': {'state': 'TX', 'county': 'Travis County', 'city': 'Austin'},
            
            # Florida
            '33101': {'state': 'FL', 'county': 'Miami-Dade County', 'city': 'Miami'},
            '33102': {'state': 'FL', 'county': 'Miami-Dade County', 'city': 'Miami'},
            '33103': {'state': 'FL', 'county': 'Miami-Dade County', 'city': 'Miami'},
            '33109': {'state': 'FL', 'county': 'Miami-Dade County', 'city': 'Miami Beach'},
            '32801': {'state': 'FL', 'county': 'Orange County', 'city': 'Orlando'},
            '32802': {'state': 'FL', 'county': 'Orange County', 'city': 'Orlando'},
            
            # Washington
            '98101': {'state': 'WA', 'county': 'King County', 'city': 'Seattle'},
            '98102': {'state': 'WA', 'county': 'King County', 'city': 'Seattle'},
            '98103': {'state': 'WA', 'county': 'King County', 'city': 'Seattle'},
            '98104': {'state': 'WA', 'county': 'King County', 'city': 'Seattle'},
            
            # Massachusetts
            '02101': {'state': 'MA', 'county': 'Suffolk County', 'city': 'Boston'},
            '02102': {'state': 'MA', 'county': 'Suffolk County', 'city': 'Boston'},
            '02103': {'state': 'MA', 'county': 'Suffolk County', 'city': 'Boston'},
            
            # Georgia
            '30301': {'state': 'GA', 'county': 'Fulton County', 'city': 'Atlanta'},
            '30302': {'state': 'GA', 'county': 'Fulton County', 'city': 'Atlanta'},
            '30303': {'state': 'GA', 'county': 'Fulton County', 'city': 'Atlanta'},
            
            # Colorado
            '80201': {'state': 'CO', 'county': 'Denver County', 'city': 'Denver'},
            '80202': {'state': 'CO', 'county': 'Denver County', 'city': 'Denver'},
            '80203': {'state': 'CO', 'county': 'Denver County', 'city': 'Denver'},
            
            # Arizona
            '85001': {'state': 'AZ', 'county': 'Maricopa County', 'city': 'Phoenix'},
            '85002': {'state': 'AZ', 'county': 'Maricopa County', 'city': 'Phoenix'},
            '85003': {'state': 'AZ', 'county': 'Maricopa County', 'city': 'Phoenix'},
        }
        
        return mock_locations.get(zipcode)
    
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
                return False
            
            # Validate service area format
            for area in service_areas:
                if not self._validate_service_area_format(area):
                    return False
            
            user.business_config.service_areas = service_areas
            self.db.commit()
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
            # State must have valid state code
            state_code = area.get('state', '').upper()
            return state_code in US_STATES
            
        elif area_type in ['county', 'neighborhood', 'city']:
            # County/neighborhood must have state
            state_code = area.get('state', '').upper()
            if state_code not in US_STATES:
                return False
            
            # County/neighborhood must have county if type is neighborhood
            if area_type in ['neighborhood', 'city'] and not area.get('county'):
                return False
        
        return True


def validate_zipcode_for_business(db: Session, zipcode: str, business_uid: str) -> Tuple[bool, Optional[str]]:
    """Convenience function for ZIP code validation."""
    validator = ServiceAreaValidator(db)
    return validator.validate_zipcode_for_business(zipcode, business_uid)