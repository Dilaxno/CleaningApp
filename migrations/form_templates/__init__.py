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
from .post_construction import get_post_construction_template
from .outside_cleaning import get_outside_cleaning_template
from .carpet_cleaning import get_carpet_cleaning_template

__all__ = [
    "get_office_template",
    "get_retail_template",
    "get_medical_template",
    "get_gym_template",
    "get_restaurant_template",
    "get_school_template",
    "get_warehouse_template",
    "get_post_construction_template",
    "get_outside_cleaning_template",
    "get_carpet_cleaning_template",
]
