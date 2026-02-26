"""
Warehouse / Industrial Template
Cleaning for warehouse and industrial facilities
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


def get_warehouse_template():
    """Get the Warehouse / Industrial template configuration"""
    return {
        "template_id": "warehouse",
        "name": "Warehouse / Industrial",
        "description": "Cleaning for warehouse and industrial facilities.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/warehouse_industrial_abc.jpg",
        "color": "#1a1a1a",
        "template_data": {
            "sections": [
                get_universal_contact_section(),
                get_universal_property_section(),
                {
                    "id": "warehouse-specific",
                    "title": "Warehouse Details",
                    "description": "Tell us about your facility.",
                    "fields": [
                        {
                            "id": "warehouseType",
                            "label": "Type of facility",
                            "type": "select",
                            "options": [
                                "Distribution center",
                                "Manufacturing",
                                "Storage warehouse",
                                "Cold storage",
                                "Other",
                            ],
                            "required": True,
                        },
                        {
                            "id": "hasOfficeArea",
                            "label": "Office area within facility",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                        },
                        {
                            "id": "highDustAreas",
                            "label": "High dust/debris areas?",
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
