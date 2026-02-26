"""
Form Templates Module
Domain-specific template definitions for CleanEnroll
"""

from .office import get_office_template
from .retail import get_retail_template
from .medical import get_medical_template
from .gym import get_gym_template
from .restaurant import get_restaurant_template
from .school import get_school_template
from .warehouse import get_warehouse_template

__all__ = [
    "get_office_template",
    "get_retail_template",
    "get_medical_template",
    "get_gym_template",
    "get_restaurant_template",
    "get_school_template",
    "get_warehouse_template",
]
