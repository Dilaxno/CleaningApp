"""
Post-Construction Cleaning Template
Specialized cleaning after construction or renovation
"""

from .shared_sections import (
    get_universal_contact_section,
    get_universal_property_section,
    get_universal_operations_section,
    get_universal_media_section,
)


def get_post_construction_template():
    """Get the Post-Construction Cleaning template configuration"""
    return {
        "template_id": "post-construction",
        "name": "Post-Construction Cleaning",
        "description": "Specialized cleaning after construction or renovation.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/post_construction_def.jpg",
        "color": "#1a1a1a",
        "template_data": {
            "sections": [
                get_universal_contact_section(),
                get_universal_property_section(),
                {
                    "id": "construction-specific",
                    "title": "Construction Details",
                    "description": "Tell us about the construction project.",
                    "fields": [
                        {
                            "id": "projectType",
                            "label": "Type of project",
                            "type": "select",
                            "options": [
                                "New construction",
                                "Renovation",
                                "Remodel",
                                "Addition",
                                "Other",
                            ],
                            "required": True,
                        },
                        {
                            "id": "constructionPhase",
                            "label": "Construction phase",
                            "type": "select",
                            "options": [
                                "Rough clean",
                                "Final clean",
                                "Touch-up clean",
                            ],
                            "required": True,
                        },
                        {
                            "id": "debrisRemoval",
                            "label": "Debris removal required?",
                            "type": "radio",
                            "options": ["Yes", "No"],
                            "required": True,
                        },
                        {
                            "id": "targetCompletionDate",
                            "label": "Target completion date",
                            "type": "date",
                            "required": True,
                        },
                    ],
                },
                get_universal_media_section(),
                get_universal_operations_section(),
            ]
        },
    }
