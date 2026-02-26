"""
Retail Store Template
Cleaning for retail spaces and storefronts
"""

from .shared_sections import (
    get_universal_contact_section,
    get_universal_property_section,
    get_universal_restrooms_section,
    get_universal_operations_section,
    get_universal_media_section,
)


def get_retail_template():
    """Get the Retail Store template configuration"""
    return {
        "template_id": "retail",
        "name": "Retail Store",
        "description": "Cleaning for retail spaces and storefronts.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/retail_store_kcvqzp.jpg",
        "color": "#1a1a1a",
        "template_data": {
            "sections": [
                get_universal_contact_section(),
                get_universal_property_section(),
                {
                    "id": "retail-specific",
                    "title": "Retail Details",
                    "description": "Tell us about your retail space.",
                    "fields": [
                        {
                            "id": "storeType",
                            "label": "Type of retail store",
                            "type": "select",
                            "options": [
                                "Clothing/Apparel",
                                "Electronics",
                                "Grocery/Food",
                                "Home goods",
                                "Pharmacy/Health",
                                "Specialty retail",
                                "Other",
                            ],
                            "required": True,
                        },
                        {
                            "id": "estimatedDailyFootTraffic",
                            "label": "Estimated daily foot traffic",
                            "type": "select",
                            "options": ["0-100", "100-300", "300-500", "500+"],
                            "required": True,
                            "hint": "Approximate number of customers per day",
                        },
                        {
                            "id": "hasFittingRooms",
                            "label": "Fitting rooms",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": False,
                        },
                        {
                            "id": "hasStorageArea",
                            "label": "Storage/Back room area",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
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
                                "Daily",
                                "Weekly",
                                "Bi-weekly",
                                "Monthly",
                                "Custom schedule",
                            ],
                            "required": True,
                        },
                        {
                            "id": "afterHoursRequired",
                            "label": "Is after-hours cleaning required?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                        },
                    ],
                },
                get_universal_restrooms_section(),
                {
                    "id": "commercial-context",
                    "title": "Commercial Context",
                    "description": "Help us understand your retail operation.",
                    "fields": [
                        {
                            "id": "isPartOfChain",
                            "label": "Is this location part of a chain?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                        },
                        {
                            "id": "numberOfLocations",
                            "label": "Number of locations under contract",
                            "type": "number",
                            "placeholder": "5",
                            "required": False,
                            "conditionalOn": {"fieldId": "isPartOfChain", "value": "Yes"},
                            "hint": "Total locations you manage",
                        },
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
                            "id": "contractTermDuration",
                            "label": "Preferred contract term duration (months)",
                            "type": "number",
                            "placeholder": "12",
                            "required": False,
                            "hint": "Typical terms are 6, 12, or 24 months",
                        },
                    ],
                },
                get_universal_media_section(),
                get_universal_operations_section(),
            ]
        },
    }
