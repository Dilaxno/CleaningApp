"""
Outside Cleaning Template
Exterior cleaning services
"""

from .shared_sections import (
    get_universal_contact_section,
    get_universal_property_section,
    get_universal_cleaning_scope_section,
    get_universal_operations_section,
    get_universal_media_section,
    get_commercial_context_section,
)


def get_outside_cleaning_template():
    """Get the Outside Cleaning template configuration"""
    return {
        "template_id": "outside-cleaning",
        "name": "Outside Cleaning",
        "description": "Exterior cleaning services.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/outside_cleaning_ghi.jpg",
        "color": "#1a1a1a",
        "template_data": {
            "sections": [
                get_universal_contact_section(),
                get_universal_property_section(),
                {
                    "id": "exterior-specific",
                    "title": "Exterior Cleaning Details",
                    "description": "Tell us about your exterior cleaning needs.",
                    "fields": [
                        {
                            "id": "servicesNeeded",
                            "label": "Services needed",
                            "type": "multiselect",
                            "options": [
                                "Window washing",
                                "Pressure washing",
                                "Gutter cleaning",
                                "Parking lot cleaning",
                                "Sidewalk cleaning",
                                "Other",
                            ],
                            "required": True,
                            "hint": "Select all that apply",
                        },
                        {
                            "id": "buildingHeight",
                            "label": "Building height (stories)",
                            "type": "number",
                            "placeholder": "2",
                            "required": True,
                        },
                        {
                            "id": "requiresLift",
                            "label": "Requires lift/scaffolding?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                        },
                    ],
                },
                get_universal_cleaning_scope_section(),
                get_commercial_context_section(),
                get_universal_media_section(),
                get_universal_operations_section(),
            ]
        },
    }
