"""
Office / Building Template
Professional cleaning for offices and commercial spaces
"""

from .shared_sections import (
    get_universal_contact_section,
    get_universal_property_section,
    get_universal_restrooms_section,
    get_universal_operations_section,
    get_universal_media_section,
    get_commercial_context_section,
)


def get_office_template():
    """Get the Office / Building template configuration"""
    return {
        "template_id": "office",
        "name": "Office / Building",
        "description": "Professional cleaning for offices and commercial spaces.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/commercial_office_jf1pvb.jpg",
        "color": "#1a1a1a",
        "template_data": {
            "sections": [
                get_universal_contact_section(),
                get_universal_property_section(),
                {
                    "id": "office-specific-details",
                    "title": "Workspace Details",
                    "description": "Tell us about your office layout.",
                    "fields": [
                        {
                            "id": "numberOfPrivateOffices",
                            "label": "Number of private offices",
                            "type": "number",
                            "placeholder": "10",
                            "required": True,
                        },
                        {
                            "id": "numberOfWorkstations",
                            "label": "Number of open workstations / cubicles",
                            "type": "number",
                            "placeholder": "25",
                            "required": True,
                        },
                        {
                            "id": "numberOfConferenceRooms",
                            "label": "Number of conference rooms",
                            "type": "number",
                            "placeholder": "3",
                            "required": True,
                        },
                        {
                            "id": "hasReceptionArea",
                            "label": "Reception area",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": False,
                        },
                        {
                            "id": "hasBreakroom",
                            "label": "Breakroom / Kitchenette",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": False,
                        },
                    ],
                },
                {
                    "id": "floor-details",
                    "title": "Floor Type",
                    "description": "Information about your flooring.",
                    "fields": [
                        {
                            "id": "primaryFloorTypes",
                            "label": "Primary floor types",
                            "type": "multiselect",
                            "options": [
                                "Carpet",
                                "Tile",
                                "VCT",
                                "Hardwood",
                                "Concrete",
                                "Mixed",
                            ],
                            "required": True,
                            "hint": "Select all that apply",
                        },
                        {
                            "id": "requiresFloorPolishing",
                            "label": "Requires floor polishing?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": False,
                        },
                    ],
                },
                {
                    "id": "office-addons",
                    "title": "Add-ons",
                    "description": "Additional services for your office.",
                    "fields": [
                        {
                            "id": "interiorWindowCleaning",
                            "label": "Interior window cleaning",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": False,
                        },
                        {
                            "id": "wasteSetup",
                            "label": "Waste setup",
                            "type": "select",
                            "options": [
                                "Individual bins only",
                                "Central bins",
                                "Dumpster on-site",
                                "Compactor",
                                "Other",
                            ],
                            "required": True,
                        },
                        {
                            "id": "highTouchDisinfection",
                            "label": "High-touch disinfection required?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": False,
                        },
                    ],
                },
                {
                    "id": "cleaning-scope",
                    "title": "Cleaning Scope",
                    "description": "Tell us about your cleaning needs.",
                    "fields": [
                        {
                            "id": "cleaningFrequency",
                            "label": "How often do you need cleaning?",
                            "type": "select",
                            "options": [
                                "Weekly",
                                "Bi-weekly",
                                "Monthly",
                                "Custom schedule",
                            ],
                            "required": True,
                        },
                        {
                            "id": "afterHoursRequired",
                            "label": "Are after-hours services required?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                        },
                    ],
                },
                get_universal_restrooms_section(),
                get_commercial_context_section(),
                get_universal_media_section(),
                get_universal_operations_section(),
            ]
        },
    }
