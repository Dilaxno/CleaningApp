"""
School / Daycare Template
Cleaning for educational facilities
"""

from .shared_sections import (
    get_universal_contact_section,
    get_universal_property_section,
    get_universal_cleaning_scope_section,
    get_universal_restrooms_section,
    get_universal_operations_section,
    get_universal_media_section,
    get_commercial_context_section,
)


def get_school_template():
    """Get the School / Daycare template configuration"""
    return {
        "template_id": "school",
        "name": "School / Daycare",
        "description": "Cleaning for educational facilities.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/school_daycare_xyz123.jpg",
        "color": "#1a1a1a",
        "template_data": {
            "sections": [
                get_universal_contact_section(),
                get_universal_property_section(),
                {
                    "id": "school-specific",
                    "title": "Educational Facility Details",
                    "description": "Tell us about your facility.",
                    "fields": [
                        {
                            "id": "facilityType",
                            "label": "Type of facility",
                            "type": "select",
                            "options": [
                                "Daycare",
                                "Preschool",
                                "Elementary school",
                                "Middle/High school",
                                "Other",
                            ],
                            "required": True,
                        },
                        {
                            "id": "numberOfClassrooms",
                            "label": "Number of classrooms",
                            "type": "number",
                            "placeholder": "10",
                            "required": True,
                        },
                        {
                            "id": "childSafeProducts",
                            "label": "Child-safe cleaning products required?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                        },
                    ],
                },
                get_universal_cleaning_scope_section(),
                get_universal_restrooms_section(),
                get_commercial_context_section(),
                get_universal_media_section(),
                get_universal_operations_section(),
            ]
        },
    }
