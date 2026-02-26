"""
Restaurant / Cafe Template
Cleaning for food service establishments
"""

from .shared_sections import (
    get_universal_contact_section,
    get_universal_property_section,
    get_universal_restrooms_section,
    get_universal_operations_section,
)


def get_restaurant_template():
    """Get the Restaurant / Cafe template configuration"""
    return {
        "template_id": "restaurant",
        "name": "Restaurant / Cafe",
        "description": "Cleaning for food service establishments.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/restaurant_cafe_abcdef.jpg",
        "color": "#1a1a1a",
        "template_data": {
            "sections": [
                get_universal_contact_section(),
                get_universal_property_section(),
                {
                    "id": "restaurant-specific",
                    "title": "Restaurant Details",
                    "description": "Tell us about your establishment.",
                    "fields": [
                        {
                            "id": "establishmentType",
                            "label": "Type of establishment",
                            "type": "select",
                            "options": [
                                "Full-service restaurant",
                                "Fast casual",
                                "Cafe/Coffee shop",
                                "Bar/Pub",
                                "Quick service",
                                "Food hall/Ghost kitchen",
                                "Other",
                            ],
                            "required": True,
                        },
                        {
                            "id": "numberOfSeats",
                            "label": "Seating capacity",
                            "type": "number",
                            "placeholder": "50",
                            "required": True,
                        },
                        {
                            "id": "operatingHours",
                            "label": "Operating hours",
                            "type": "text",
                            "placeholder": "e.g., 11am-10pm daily",
                            "required": True,
                            "hint": "When is the restaurant open?",
                        },
                        {
                            "id": "backOfHouseIncluded",
                            "label": "Back-of-house cleaning included?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                            "hint": "Kitchen, prep areas, dishwashing station",
                        },
                        {
                            "id": "kitchenCleaning",
                            "label": "Kitchen deep cleaning required?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                            "conditionalOn": {
                                "fieldId": "backOfHouseIncluded",
                                "value": "Yes",
                            },
                        },
                        {
                            "id": "greaseLevel",
                            "label": "Grease level",
                            "type": "select",
                            "options": ["Low", "Moderate", "Heavy"],
                            "required": True,
                            "conditionalOn": {
                                "fieldId": "backOfHouseIncluded",
                                "value": "Yes",
                            },
                            "hint": "Typical grease buildup from cooking operations",
                        },
                        {
                            "id": "hoodDuctExhaustCleaning",
                            "label": "Hood/duct/exhaust cleaning included?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                            "conditionalOn": {
                                "fieldId": "backOfHouseIncluded",
                                "value": "Yes",
                            },
                            "hint": "Hood/exhaust work requires manual review and specialized protocols",
                        },
                    ],
                },
                {
                    "id": "cleaning-scope",
                    "title": "Cleaning Requirements",
                    "description": "Specify your cleaning needs and schedule.",
                    "fields": [
                        {
                            "id": "cleaningFrequency",
                            "label": "Cleaning frequency",
                            "type": "select",
                            "options": [
                                "Daily",
                                "5x per week",
                                "3x per week",
                                "2x per week",
                                "Weekly",
                                "Custom schedule",
                            ],
                            "required": True,
                        },
                        {
                            "id": "customFrequencyDetails",
                            "label": "Custom schedule details",
                            "type": "textarea",
                            "placeholder": "Describe your preferred cleaning schedule",
                            "required": False,
                            "conditionalOn": {
                                "fieldId": "cleaningFrequency",
                                "value": "Custom schedule",
                            },
                        },
                        {
                            "id": "cleaningWindow",
                            "label": "Cleaning window",
                            "type": "select",
                            "options": [
                                "After close",
                                "Before open",
                                "Between shifts",
                                "During business hours",
                                "Flexible",
                            ],
                            "required": True,
                            "hint": "When should cleaning occur?",
                        },
                        {
                            "id": "hasDiningArea",
                            "label": "Dining area cleaning required?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                        },
                        {
                            "id": "hasBar",
                            "label": "Bar area cleaning required?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": False,
                        },
                    ],
                },
                get_universal_restrooms_section(),
                {
                    "id": "commercial-context",
                    "title": "Contract Information",
                    "description": "Help us structure your service agreement.",
                    "fields": [
                        {
                            "id": "hasCurrentProvider",
                            "label": "Do you currently have a cleaning provider?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                        },
                        {
                            "id": "currentContractExpires",
                            "label": "Current contract expiration date",
                            "type": "date",
                            "required": False,
                            "conditionalOn": {
                                "fieldId": "hasCurrentProvider",
                                "value": "Yes",
                            },
                            "hint": "This helps us plan the transition timeline",
                        },
                        {
                            "id": "preferredTerm",
                            "label": "Preferred contract term",
                            "type": "select",
                            "options": [
                                "Month-to-month",
                                "6 months",
                                "12 months",
                                "24 months",
                                "Custom term",
                            ],
                            "required": True,
                        },
                        {
                            "id": "customTermNotes",
                            "label": "Custom term details",
                            "type": "text",
                            "placeholder": "e.g., 18 months, seasonal contract",
                            "required": False,
                            "conditionalOn": {"fieldId": "preferredTerm", "value": "Custom term"},
                        },
                        {
                            "id": "isPartOfChain",
                            "label": "Is this part of a multi-location restaurant group?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                        },
                        {
                            "id": "numberOfLocations",
                            "label": "Number of locations",
                            "type": "number",
                            "placeholder": "3",
                            "required": False,
                            "conditionalOn": {"fieldId": "isPartOfChain", "value": "Yes"},
                        },
                    ],
                },
                {
                    "id": "media-uploads",
                    "title": "Restaurant Photos",
                    "description": "Photos help us provide accurate quotes (optional but recommended).",
                    "fields": [
                        {
                            "id": "propertyShots",
                            "label": "Restaurant photos",
                            "type": "file",
                            "accept": "image/*",
                            "required": False,
                            "multiple": True,
                            "maxFiles": 10,
                            "uploadMode": "client-r2",
                            "hint": "Upload photos of dining area, kitchen, and other spaces to be cleaned",
                        },
                    ],
                },
                get_universal_operations_section(),
            ]
        },
    }
