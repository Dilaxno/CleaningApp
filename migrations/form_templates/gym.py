"""
Gym / Fitness Center Template
Cleaning for fitness facilities
"""

from .shared_sections import (
    get_universal_contact_section,
    get_universal_property_section,
    get_universal_operations_section,
)


def get_gym_template():
    """Get the Gym / Fitness Center template configuration"""
    return {
        "template_id": "gym",
        "name": "Gym / Fitness Center",
        "description": "Cleaning for fitness facilities.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/gym_fitness_center_qwerty.jpg",
        "color": "#1a1a1a",
        "template_data": {
            "sections": [
                get_universal_contact_section(),
                get_universal_property_section(),
                {
                    "id": "gym-specific",
                    "title": "Facility Details",
                    "description": "Tell us about your fitness facility.",
                    "fields": [
                        {
                            "id": "facilityType",
                            "label": "Facility type",
                            "type": "select",
                            "options": [
                                "Full-service gym",
                                "Boutique fitness studio",
                                "CrossFit/Functional training",
                                "Yoga/Pilates studio",
                                "Martial arts facility",
                                "Recreation center",
                                "Other",
                            ],
                            "required": True,
                        },
                        {
                            "id": "numberOfMembers",
                            "label": "Approximate member count",
                            "type": "select",
                            "options": [
                                "Under 100",
                                "100-300",
                                "300-500",
                                "500-1000",
                                "1000+",
                            ],
                            "required": True,
                        },
                        {
                            "id": "memberTrafficLevel",
                            "label": "Member traffic level",
                            "type": "select",
                            "options": ["Low", "Moderate", "High"],
                            "required": True,
                            "hint": "Overall daily foot traffic intensity",
                        },
                        {
                            "id": "peakHours",
                            "label": "Peak hours",
                            "type": "text",
                            "placeholder": "e.g., 6-9am, 5-8pm",
                            "required": True,
                            "hint": "When is the facility busiest?",
                        },
                        {
                            "id": "facilityZones",
                            "label": "Facility zones requiring cleaning",
                            "type": "multiselect",
                            "options": [
                                "Cardio area",
                                "Free weights",
                                "Group studio",
                                "Turf area",
                                "Locker rooms",
                                "Showers",
                                "Sauna/Steam room",
                                "Childcare area",
                                "Offices/Reception",
                            ],
                            "required": True,
                            "hint": "Select all that apply",
                        },
                        {
                            "id": "equipmentCount",
                            "label": "Approximate equipment count",
                            "type": "number",
                            "placeholder": "50",
                            "required": True,
                            "hint": "Total machines, benches, and major equipment pieces",
                        },
                        {
                            "id": "equipmentTypeNotes",
                            "label": "Equipment type notes",
                            "type": "textarea",
                            "placeholder": "e.g., Mostly cardio machines, heavy free weights, specialized equipment",
                            "required": False,
                        },
                        {
                            "id": "numberOfRestrooms",
                            "label": "Number of restrooms",
                            "type": "number",
                            "placeholder": "4",
                            "required": True,
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
                                "Custom recurring schedule",
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
                                "value": "Custom recurring schedule",
                            },
                        },
                        {
                            "id": "preferredServiceTime",
                            "label": "Preferred service time",
                            "type": "select",
                            "options": [
                                "After hours (evenings)",
                                "Early morning (before opening)",
                                "During business hours",
                                "Overnight",
                                "Flexible",
                            ],
                            "required": True,
                        },
                        {
                            "id": "equipmentSanitization",
                            "label": "Equipment sanitization required?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                        },
                        {
                            "id": "consumablesResponsibility",
                            "label": "Cleaning supplies & consumables",
                            "type": "select",
                            "options": [
                                "Client provides",
                                "Provider provides",
                                "Hybrid (shared responsibility)",
                            ],
                            "required": True,
                            "hint": "Who supplies paper products, sanitizers, etc.?",
                        },
                    ],
                },
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
                            "id": "isPartOfChain",
                            "label": "Is this part of a multi-location chain?",
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
                    "title": "Facility Photos",
                    "description": "Photos help us provide accurate quotes (optional but recommended).",
                    "fields": [
                        {
                            "id": "propertyShots",
                            "label": "Facility photos",
                            "type": "file",
                            "accept": "image/*",
                            "required": False,
                            "multiple": True,
                            "maxFiles": 10,
                            "uploadMode": "client-r2",
                            "hint": "Upload photos of workout areas, locker rooms, and other spaces",
                        },
                    ],
                },
                get_universal_operations_section(),
            ]
        },
    }
