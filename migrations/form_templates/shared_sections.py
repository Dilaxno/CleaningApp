"""
Shared form sections used across multiple templates
These are reusable building blocks for form templates
"""


def get_universal_contact_section():
    """Universal Contact Information Section"""
    return {
        "id": "client-info",
        "title": "Contact Information",
        "description": "Let's start with your details.",
        "fields": [
            {
                "id": "contactName",
                "label": "Contact person name",
                "type": "text",
                "placeholder": "John Smith",
                "required": True,
            },
            {
                "id": "businessName",
                "label": "Business / Client name",
                "type": "text",
                "placeholder": "Acme Corporation",
                "required": True,
            },
            {
                "id": "email",
                "label": "Email address",
                "type": "email",
                "placeholder": "john@acme.com",
                "required": True,
            },
            {
                "id": "phone",
                "label": "Phone number",
                "type": "tel",
                "placeholder": "(555) 123-4567",
                "required": True,
            },
            {
                "id": "serviceAddress",
                "label": "Service address",
                "type": "textarea",
                "placeholder": "123 Main St, Suite 100, City, State ZIP",
                "required": True,
            },
        ],
    }


def get_universal_property_section():
    """Universal Property Details Section"""
    return {
        "id": "property-details",
        "title": "Property Details",
        "description": "Tell us about your space.",
        "fields": [
            {
                "id": "squareFootage",
                "label": "Square footage",
                "type": "number",
                "placeholder": "5000",
                "required": True,
                "hint": "Approximate total area to be cleaned",
            },
            {
                "id": "numberOfFloors",
                "label": "Number of floors",
                "type": "number",
                "placeholder": "2",
                "required": True,
                "min": 1,
            },
            {
                "id": "elevatorAvailable",
                "label": "Is there an elevator available?",
                "type": "radio",
                "options": ["Yes", "No"],
                "required": True,
            },
        ],
    }


def get_universal_cleaning_scope_section():
    """Universal Cleaning Scope Section"""
    return {
        "id": "cleaning-scope",
        "title": "Cleaning Scope",
        "description": "Tell us about your cleaning needs.",
        "fields": [
            {
                "id": "cleaningFrequency",
                "label": "How often do you need cleaning?",
                "type": "select",
                "options": ["Weekly", "Bi-weekly", "Monthly", "Custom schedule"],
                "required": True,
            },
            {
                "id": "preferredServiceTime",
                "label": "Preferred service time",
                "type": "radio",
                "options": ["Business hours", "After hours"],
                "required": True,
            },
            {
                "id": "cleaningLevel",
                "label": "Cleaning level needed",
                "type": "slider",
                "min": 1,
                "max": 3,
                "sliderLabels": [
                    "https://res.cloudinary.com/dxqum9ywx/image/upload/v1770252734/Heavy_duty_clean_z58dty.svg",
                    "https://res.cloudinary.com/dxqum9ywx/image/upload/v1770252734/standard_clean_q0m5fm.svg",
                    "https://res.cloudinary.com/dxqum9ywx/image/upload/v1770252734/light_touch_up_gsb0ho.svg",
                ],
                "required": True,
                "hint": "This helps us estimate the time and effort needed",
            },
        ],
    }


def get_universal_restrooms_section():
    """Universal Restrooms Section with Conditional Logic"""
    return {
        "id": "restrooms",
        "title": "Restrooms",
        "description": "Information about restroom facilities.",
        "fields": [
            {
                "id": "hasRestrooms",
                "label": "Are there restrooms on site?",
                "type": "radio",
                "options": ["Yes", "No"],
                "required": True,
            },
            {
                "id": "numberOfRestrooms",
                "label": "Number of restrooms",
                "type": "number",
                "placeholder": "4",
                "required": True,
                "conditionalOn": {"fieldId": "hasRestrooms", "value": "Yes"},
            },
            {
                "id": "restroomCondition",
                "label": "Restroom condition",
                "type": "select",
                "options": ["Light", "Moderate", "Heavy"],
                "required": True,
                "conditionalOn": {"fieldId": "hasRestrooms", "value": "Yes"},
            },
        ],
    }


def get_universal_operations_section():
    """Universal Operations Section"""
    return {
        "id": "operations",
        "title": "Operations",
        "description": "Logistics and special requirements.",
        "fields": [
            {
                "id": "accessMethod",
                "label": "Access method",
                "type": "select",
                "options": ["Key", "Access code", "On-site staff", "Other"],
                "required": True,
            },
            {
                "id": "specialInstructions",
                "label": "Special instructions",
                "type": "textarea",
                "placeholder": "Any specific requirements, areas to focus on, or things we should know...",
                "required": False,
                "maxLength": 1000,
            },
        ],
    }


def get_universal_media_section():
    """Universal Media Upload Section - Property Photos and Video Walkthrough"""
    return {
        "id": "media-uploads",
        "title": "Property Media",
        "description": "Help us understand your space better.",
        "fields": [
            {
                "id": "propertyShots",
                "label": "Property photos",
                "type": "file",
                "accept": "image/*",
                "required": True,
                "multiple": True,
                "maxFiles": 10,
                "uploadMode": "client-r2",
                "hint": "Upload at least 2 photos of the property to help us provide an accurate quote",
            },
        ],
    }


def get_commercial_context_section():
    """Commercial Context Section - for understanding client's current situation"""
    return {
        "id": "commercial-context",
        "title": "Commercial Context",
        "description": "Help us understand your current situation.",
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
                "label": "When does your current contract expire?",
                "type": "date",
                "required": False,
                "conditionalOn": {"fieldId": "hasCurrentProvider", "value": "Yes"},
                "hint": "This helps us plan the transition timeline",
            },
            {
                "id": "isMultiLocation",
                "label": "Is this part of a multi-location portfolio?",
                "type": "radio",
                "options": ["Yes", "No"],
                "required": True,
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
    }
