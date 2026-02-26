"""
Carpet Cleaning Template
Specialized carpet cleaning services
"""

from .shared_sections import (
    get_universal_contact_section,
    get_universal_property_section,
    get_universal_operations_section,
    get_universal_media_section,
    get_commercial_context_section,
)


def get_carpet_cleaning_template():
    """Get the Carpet Cleaning template configuration"""
    return {
        "template_id": "carpet-cleaning",
        "name": "Carpet Cleaning",
        "description": "Specialized carpet cleaning services.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/carpet_cleaning_jkl.jpg",
        "color": "#1a1a1a",
        "template_data": {
            "sections": [
                get_universal_contact_section(),
                get_universal_property_section(),
                {
                    "id": "carpet-specific",
                    "title": "Carpet Cleaning Details",
                    "description": "Tell us about your carpet cleaning needs.",
                    "fields": [
                        {
                            "id": "carpetSquareFootage",
                            "label": "Carpet square footage",
                            "type": "number",
                            "placeholder": "2000",
                            "required": True,
                        },
                        {
                            "id": "carpetCondition",
                            "label": "Carpet condition",
                            "type": "select",
                            "options": [
                                "Light soiling",
                                "Moderate soiling",
                                "Heavy soiling",
                                "Stains present",
                            ],
                            "required": True,
                        },
                        {
                            "id": "cleaningMethod",
                            "label": "Preferred cleaning method",
                            "type": "select",
                            "options": [
                                "Steam cleaning",
                                "Dry cleaning",
                                "No preference",
                            ],
                            "required": True,
                        },
                        {
                            "id": "cleaningFrequency",
                            "label": "How often do you need carpet cleaning?",
                            "type": "select",
                            "options": [
                                "One-time",
                                "Quarterly",
                                "Semi-annually",
                                "Annually",
                            ],
                            "required": True,
                        },
                    ],
                },
                get_commercial_context_section(),
                get_universal_media_section(),
                get_universal_operations_section(),
            ]
        },
    }
