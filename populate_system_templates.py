#!/usr/bin/env python3
"""
Script to populate the database with system templates from the hardcoded templates.
This should be run once after the database migration to convert existing templates.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import FormTemplate
# Import all models to ensure relationships are properly set up
from app import models
from app import models_invoice

# Template data - converted from the frontend templates.ts
SYSTEM_TEMPLATES = [
    {
        "template_id": "office",
        "name": "Office / Commercial",
        "description": "Professional cleaning for offices and commercial spaces.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/commercial_office_jf1pvb.jpg",
        "color": "#1a1a1a",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True},
                    {"id": "companyName", "label": "Company name", "type": "text", "placeholder": "Acme Corporation", "required": True},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@acme.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Property address", "type": "textarea", "placeholder": "123 Main St, Suite 100, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "property-details",
                "title": "Property Details",
                "description": "Tell us about your space.",
                "fields": [
                    {"id": "squareFootage", "label": "Approximate square footage", "type": "number", "placeholder": "5000", "required": True},
                    {"id": "floorTypes", "label": "Main floor type", "type": "select", "options": ["Carpet", "Tile", "Hardwood", "Vinyl", "Mixed"], "required": True},
                    {"id": "numberOfRestrooms", "label": "Number of restrooms", "type": "number", "placeholder": "4"},
                    {"id": "cleanlinessLevel", "label": "How would you rate the current cleanliness?", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Duty Clean", "Standard Clean", "Light Touch-Up"], "required": True, "hint": "This helps us estimate the time and effort needed"},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Needs",
                "description": "What cleaning services do you need?",
                "fields": [
                    {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["One-time", "Daily", "3x per week", "Weekly", "Bi-weekly", "Monthly"], "required": True},
                    {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?"},
                    {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False},
                    {"id": "preferredServiceTime", "label": "Preferred time", "type": "select", "options": ["Morning", "Afternoon", "Evening", "After hours"], "required": True},
                    {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like"},
                    {
                        "id": "propertyShots",
                        "label": "Property photos",
                        "type": "file",
                        "required": True,
                        "accept": "image/*",
                        "multiple": True,
                        "maxFiles": 10,
                        "uploadMode": "client-r2",
                        "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business. Minimum 2 photos, maximum 10 photos, 50MB per image."
                    },
                    {"id": "specialRequests", "label": "Any special requests or notes?", "type": "textarea", "placeholder": "Eco-friendly products, specific areas of focus, etc."},
                ]
            }
        ]
    },
    {
        "template_id": "retail",
        "name": "Retail Store",
        "description": "Specialized cleaning for retail environments.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087527/Retail_Store_ixqhqj.webp",
        "color": "#e74c3c",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "Jane Smith", "required": True},
                    {"id": "companyName", "label": "Store name", "type": "text", "placeholder": "Fashion Boutique", "required": True},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "jane@boutique.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Store address", "type": "textarea", "placeholder": "456 Shopping Ave, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "property-details",
                "title": "Store Details",
                "description": "Tell us about your retail space.",
                "fields": [
                    {"id": "squareFootage", "label": "Store square footage", "type": "number", "placeholder": "2500", "required": True},
                    {"id": "storeType", "label": "Type of retail store", "type": "select", "options": ["Clothing", "Electronics", "Grocery", "Restaurant", "Beauty", "Other"], "required": True},
                    {"id": "customerTraffic", "label": "Daily customer traffic", "type": "select", "options": ["Low (0-50)", "Medium (50-200)", "High (200+)"], "required": True},
                    {"id": "cleanlinessLevel", "label": "Current cleanliness level", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Needs Deep Clean", "Standard", "Well Maintained"], "required": True},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Needs",
                "description": "What cleaning services do you need?",
                "fields": [
                    {"id": "cleaningFrequency", "label": "Cleaning frequency", "type": "select", "options": ["One-time", "Daily", "3x per week", "Weekly", "Bi-weekly", "Monthly"], "required": True},
                    {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False},
                    {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False},
                    {"id": "operatingHours", "label": "Store operating hours", "type": "text", "placeholder": "9 AM - 9 PM", "required": True},
                    {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like"},
                    {
                        "id": "propertyShots",
                        "label": "Property photos",
                        "type": "file",
                        "required": True,
                        "accept": "image/*",
                        "multiple": True,
                        "maxFiles": 10,
                        "uploadMode": "client-r2",
                        "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business. Minimum 2 photos, maximum 10 photos, 50MB per image."
                    },
                    {"id": "specialRequests", "label": "Any special requests?", "type": "textarea", "placeholder": "Window cleaning, display dusting, etc."},
                ]
            }
        ]
    },
    {
        "template_id": "medical",
        "name": "Medical / Dental Clinic",
        "description": "Specialized cleaning for healthcare facilities.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087527/Medical_Dental_Clinic_ixqhqj.webp",
        "color": "#27ae60",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "Dr. Smith", "required": True},
                    {"id": "practiceName", "label": "Practice name", "type": "text", "placeholder": "Smith Medical Center", "required": True},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "admin@smithmedical.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Facility address", "type": "textarea", "placeholder": "789 Health Blvd, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "facility-details",
                "title": "Facility Details",
                "description": "Tell us about your medical facility.",
                "fields": [
                    {"id": "squareFootage", "label": "Facility square footage", "type": "number", "placeholder": "3000", "required": True},
                    {"id": "facilityType", "label": "Type of facility", "type": "select", "options": ["General Practice", "Dental", "Specialist", "Urgent Care", "Surgery Center"], "required": True},
                    {"id": "numberOfRooms", "label": "Number of treatment rooms", "type": "number", "placeholder": "8", "required": True},
                    {"id": "patientVolume", "label": "Daily patient volume", "type": "select", "options": ["Low (0-20)", "Medium (20-50)", "High (50+)"], "required": True},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Needs",
                "description": "What cleaning services do you need?",
                "fields": [
                    {"id": "cleaningFrequency", "label": "Cleaning frequency", "type": "select", "options": ["One-time", "Daily", "3x per week", "Weekly", "Bi-weekly", "Monthly"], "required": True},
                    {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False},
                    {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False},
                    {"id": "disinfectionLevel", "label": "Required disinfection level", "type": "select", "options": ["Standard", "Hospital Grade", "CDC Compliant"], "required": True},
                    {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like"},
                    {
                        "id": "propertyShots",
                        "label": "Property photos",
                        "type": "file",
                        "required": True,
                        "accept": "image/*",
                        "multiple": True,
                        "maxFiles": 10,
                        "uploadMode": "client-r2",
                        "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business. Minimum 2 photos, maximum 10 photos, 50MB per image."
                    },
                    {"id": "specialRequests", "label": "Special requirements or notes", "type": "textarea", "placeholder": "Disinfection protocols, restricted areas, etc."},
                ]
            }
        ]
    },
    {
        "template_id": "residential",
        "name": "Residential / Home",
        "description": "House cleaning services for homes and apartments.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087527/Residential_Home_ixqhqj.webp",
        "color": "#3498db",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@email.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Home address", "type": "textarea", "placeholder": "123 Main St, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "property-details",
                "title": "Home Details",
                "description": "Tell us about your home.",
                "fields": [
                    {"id": "squareFootage", "label": "Home square footage", "type": "number", "placeholder": "2000", "required": True},
                    {"id": "bedrooms", "label": "Number of bedrooms", "type": "number", "placeholder": "3", "required": True},
                    {"id": "bathrooms", "label": "Number of bathrooms", "type": "number", "placeholder": "2", "required": True},
                    {"id": "floors", "label": "Number of floors", "type": "number", "placeholder": "2", "required": True},
                    {"id": "pets", "label": "Do you have pets?", "type": "radio", "options": ["Yes", "No"], "required": True},
                    {"id": "cleanlinessLevel", "label": "Current cleanliness level", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Needs Deep Clean", "Standard", "Well Maintained"], "required": True},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Needs",
                "description": "What cleaning services do you need?",
                "fields": [
                    {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["One-time", "Weekly", "Bi-weekly", "Monthly"], "required": True},
                    {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False},
                    {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False},
                    {"id": "preferredServiceTime", "label": "Preferred time", "type": "select", "options": ["Morning", "Afternoon", "Evening"], "required": True},
                    {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like"},
                    {
                        "id": "propertyShots",
                        "label": "Property photos",
                        "type": "file",
                        "required": True,
                        "accept": "image/*",
                        "multiple": True,
                        "maxFiles": 10,
                        "uploadMode": "client-r2",
                        "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business. Minimum 2 photos, maximum 10 photos, 50MB per image."
                    },
                    {"id": "specialRequests", "label": "Any special requests?", "type": "textarea", "placeholder": "Specific rooms, eco-friendly products, pet considerations, etc."},
                ]
            }
        ]
    },
    {
        "template_id": "deep-clean",
        "name": "Deep Clean",
        "description": "Comprehensive deep cleaning service for thorough sanitization.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1770038049/deep_clean_tvl1an.jpg",
        "color": "#9b59b6",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@email.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Property address", "type": "textarea", "placeholder": "123 Main St, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "property-details",
                "title": "Property Details",
                "description": "Tell us about your property.",
                "fields": [
                    {"id": "propertyType", "label": "Property type", "type": "select", "options": ["Residential Home", "Apartment", "Condo", "Office", "Commercial Space", "Other"], "required": True},
                    {"id": "squareFootage", "label": "Approximate square footage", "type": "number", "placeholder": "2000", "required": True},
                    {"id": "bedrooms", "label": "Number of bedrooms", "type": "number", "placeholder": "3"},
                    {"id": "bathrooms", "label": "Number of bathrooms", "type": "number", "placeholder": "2"},
                    {"id": "lastDeepClean", "label": "When was the last deep clean?", "type": "select", "options": ["Never", "6+ months ago", "3-6 months ago", "1-3 months ago", "Less than 1 month ago"], "required": True},
                    {"id": "cleanlinessLevel", "label": "Current condition", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Duty Required", "Moderate Cleaning", "Light Deep Clean"], "required": True},
                ]
            },
            {
                "id": "deep-clean-specifics",
                "title": "Deep Clean Specifications",
                "description": "What areas need deep cleaning attention?",
                "fields": [
                    {"id": "deepCleanAreas", "label": "Areas requiring deep clean", "type": "checkbox", "options": ["Kitchen (appliances, cabinets)", "Bathrooms (tiles, grout)", "Bedrooms (baseboards, windows)", "Living areas (furniture, carpets)", "Basement/Attic", "Garage"], "required": True},
                    {"id": "applianceCleaning", "label": "Appliance cleaning needed", "type": "checkbox", "options": ["Oven interior", "Refrigerator interior", "Microwave", "Dishwasher", "Washing machine", "Dryer"]},
                    {"id": "specialConcerns", "label": "Special concerns or problem areas", "type": "textarea", "placeholder": "Pet odors, stains, mold, heavy grease, etc."},
                    {"id": "cleaningProducts", "label": "Cleaning product preferences", "type": "radio", "options": ["Standard products", "Eco-friendly only", "Bring your own products"], "required": True},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Requirements",
                "description": "When and how do you need this service?",
                "fields": [
                    {"id": "urgency", "label": "How soon do you need this service?", "type": "select", "options": ["ASAP (within 24-48 hours)", "This week", "Next week", "Within 2 weeks", "Flexible timing"], "required": True},
                    {"id": "accessInstructions", "label": "Property access instructions", "type": "textarea", "placeholder": "Key location, gate codes, parking instructions, etc.", "required": True},
                    {"id": "selectedAddons", "label": "Additional services", "type": "addons", "required": False, "hint": "Select any additional services you'd like"},
                    {
                        "id": "propertyShots",
                        "label": "Property photos",
                        "type": "file",
                        "required": True,
                        "accept": "image/*",
                        "multiple": True,
                        "maxFiles": 10,
                        "uploadMode": "client-r2",
                        "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business. Minimum 2 photos, maximum 10 photos, 50MB per image."
                    },
                    {"id": "specialRequests", "label": "Special requests or concerns", "type": "textarea", "placeholder": "Pet-safe products, allergies, fragile items, specific cleaning products to avoid, etc.", "required": False},
                ]
            }
        ]
    }
]


def populate_system_templates():
    """Populate the database with system templates"""
    db = SessionLocal()
    try:
        print("Populating system templates...")
        
        for template_data in SYSTEM_TEMPLATES:
            # Check if template already exists
            existing = db.query(FormTemplate).filter(
                FormTemplate.template_id == template_data["template_id"],
                FormTemplate.is_system_template == True
            ).first()
            
            if existing:
                print(f"Template {template_data['template_id']} already exists, updating...")
                # Update existing template
                existing.name = template_data["name"]
                existing.description = template_data["description"]
                existing.image = template_data["image"]
                existing.color = template_data["color"]
                existing.template_data = {"sections": template_data["sections"]}
            else:
                print(f"Creating template {template_data['template_id']}...")
                # Create new template
                template = FormTemplate(
                    template_id=template_data["template_id"],
                    user_id=None,  # System template
                    name=template_data["name"],
                    description=template_data["description"],
                    image=template_data["image"],
                    color=template_data["color"],
                    is_system_template=True,
                    template_data={"sections": template_data["sections"]}
                )
                db.add(template)
        
        db.commit()
        print("System templates populated successfully!")
        
    except Exception as e:
        print(f"Error populating templates: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    populate_system_templates()