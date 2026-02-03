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
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/retail_store_h567sp.jpg",
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
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/Medical_Clinic_rnq02h.jpg",
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
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/residential_aoijhw.jpg",
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
    },
    {
        "template_id": "gym",
        "name": "Fitness Gym / Studio",
        "description": "Keep your gym fresh and clean.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087510/gym_uhy5i9.jpg",
        "color": "#f39c12",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "facilityName", "label": "Gym/Studio name", "type": "text", "placeholder": "FitLife Gym", "required": True},
                    {"id": "contactName", "label": "Contact person", "type": "text", "placeholder": "John Smith", "required": True},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@fitlife.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Facility address", "type": "textarea", "placeholder": "123 Fitness Ave, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "property-details",
                "title": "Facility Details",
                "description": "Tell us about your space.",
                "fields": [
                    {"id": "squareFootage", "label": "Total square footage", "type": "number", "placeholder": "5000", "required": True},
                    {"id": "hasLockerRooms", "label": "Locker rooms/showers?", "type": "radio", "options": ["Yes", "No"], "required": True},
                    {"id": "hasPool", "label": "Pool or sauna?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "cleanlinessLevel", "label": "How would you rate the current cleanliness?", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Duty Clean", "Standard Clean", "Light Touch-Up"], "required": True, "hint": "This helps us estimate the time and effort needed"},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Needs",
                "description": "What cleaning services do you need?",
                "fields": [
                    {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["One-time", "Daily", "Twice daily", "3x per week", "Weekly"], "required": True},
                    {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?"},
                    {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False},
                    {"id": "preferredServiceTime", "label": "Preferred time", "type": "select", "options": ["Early morning", "Midday", "Late night"], "required": True},
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
                    {"id": "specialRequests", "label": "Any special requests?", "type": "textarea", "placeholder": "Equipment sanitizing, odor control, etc."},
                ]
            }
        ]
    },
    {
        "template_id": "restaurant",
        "name": "Restaurant / Cafe",
        "description": "Professional cleaning for food service.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087529/cafe_vlqstf.webp",
        "color": "#e67e22",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "restaurantName", "label": "Restaurant/Cafe name", "type": "text", "placeholder": "The Golden Fork", "required": True},
                    {"id": "contactName", "label": "Contact person", "type": "text", "placeholder": "John Smith, Manager", "required": True},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "manager@restaurant.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Restaurant address", "type": "textarea", "placeholder": "123 Main St, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "facility-details",
                "title": "Facility Details",
                "description": "Tell us about your space.",
                "fields": [
                    {"id": "squareFootage", "label": "Total square footage", "type": "number", "placeholder": "3500", "required": True},
                    {"id": "kitchenSize", "label": "Kitchen size (sq ft)", "type": "number", "placeholder": "800", "required": True},
                    {"id": "floorTypes", "label": "Floor type", "type": "select", "options": ["Non-slip tile", "Sealed concrete", "Vinyl", "Mixed"], "required": True},
                    {"id": "cleanlinessLevel", "label": "How would you rate the current cleanliness?", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Duty Clean", "Standard Clean", "Light Touch-Up"], "required": True, "hint": "This helps us estimate the time and effort needed"},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Needs",
                "description": "What cleaning services do you need?",
                "fields": [
                    {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["One-time", "Daily", "After each shift", "Twice daily", "Weekly"], "required": True},
                    {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?"},
                    {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False},
                    {"id": "preferredServiceTime", "label": "Preferred time", "type": "select", "options": ["After closing", "Before opening", "Between shifts"], "required": True},
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
                    {"id": "specialRequests", "label": "Any special requests?", "type": "textarea", "placeholder": "Hood vent cleaning, grease trap service, etc."},
                ]
            }
        ]
    },
    {
        "template_id": "airbnb",
        "name": "Airbnb / Short-Term Rental",
        "description": "Turnover cleaning for vacation rentals.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/Airbnb_qopjpn.jpg",
        "color": "#ff5a5f",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True},
                    {"id": "companyName", "label": "Property management company (if any)", "type": "text", "placeholder": "Smith Rentals LLC"},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@email.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Property address", "type": "textarea", "placeholder": "123 Vacation Lane, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "property-details",
                "title": "Property Details",
                "description": "Tell us about your rental.",
                "fields": [
                    {"id": "squareFootage", "label": "Approximate square footage", "type": "number", "placeholder": "1500", "required": True},
                    {"id": "bedrooms", "label": "Number of bedrooms", "type": "number", "placeholder": "3", "required": True},
                    {"id": "bathrooms", "label": "Number of bathrooms", "type": "number", "placeholder": "2", "required": True},
                    {"id": "propertyType", "label": "Property type", "type": "select", "options": ["House", "Apartment", "Condo", "Cabin", "Studio"], "required": True},
                    {"id": "hasOutdoorSpace", "label": "Outdoor space (patio/deck)?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "cleanlinessLevel", "label": "How would you rate the current cleanliness?", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Very Messy", "Moderately Dirty", "Lightly Cluttered"], "required": True, "hint": "This helps us estimate the time and effort needed"},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Needs",
                "description": "What cleaning services do you need?",
                "fields": [
                    {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["Per turnover", "Weekly", "Bi-weekly", "On-demand"], "required": True},
                    {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?"},
                    {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False},
                    {"id": "turnaroundTime", "label": "Typical turnover window", "type": "select", "options": ["2-3 hours", "3-4 hours", "4-5 hours", "Same day"], "required": True},
                    {"id": "linensProvided", "label": "Do you need linen service?", "type": "radio", "options": ["Yes, wash linens", "Yes, replace linens", "No, guest brings own"]},
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
                    {"id": "specialRequests", "label": "Any special requests?", "type": "textarea", "placeholder": "Restock amenities, check for damages, etc."},
                ]
            }
        ]
    },
    {
        "template_id": "school",
        "name": "School / Daycare",
        "description": "Safe cleaning for educational facilities.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/school_opn4hw.jpg",
        "color": "#2ecc71",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "facilityName", "label": "School/Daycare name", "type": "text", "placeholder": "Sunshine Academy", "required": True},
                    {"id": "contactName", "label": "Contact person", "type": "text", "placeholder": "Jane Smith, Director", "required": True},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "director@school.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Facility address", "type": "textarea", "placeholder": "123 Education Blvd, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "facility-details",
                "title": "Facility Details",
                "description": "Tell us about your facility.",
                "fields": [
                    {"id": "squareFootage", "label": "Total square footage", "type": "number", "placeholder": "8000", "required": True},
                    {"id": "classroomCount", "label": "Number of classrooms", "type": "number", "placeholder": "10", "required": True},
                    {"id": "bathroomCount", "label": "Number of restrooms", "type": "number", "placeholder": "6", "required": True},
                    {"id": "facilityType", "label": "Facility type", "type": "select", "options": ["Daycare/Preschool", "Elementary School", "Middle School", "High School", "After-school Program"], "required": True},
                    {"id": "hasCafeteria", "label": "Cafeteria/Kitchen?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "hasPlayground", "label": "Indoor play area?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "cleanlinessLevel", "label": "How would you rate the current cleanliness?", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Duty Clean", "Standard Clean", "Light Touch-Up"], "required": True, "hint": "This helps us estimate the time and effort needed"},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Needs",
                "description": "What cleaning services do you need?",
                "fields": [
                    {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["Daily", "Twice daily", "Weekly", "After events"], "required": True},
                    {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?"},
                    {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False},
                    {"id": "preferredServiceTime", "label": "Preferred time", "type": "select", "options": ["After school hours", "Evening", "Weekend"], "required": True},
                    {"id": "childSafeProducts", "label": "Child-safe/non-toxic products required?", "type": "radio", "options": ["Yes", "No"], "required": True},
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
                    {"id": "specialRequests", "label": "Any special requests?", "type": "textarea", "placeholder": "Toy sanitizing, nap mat cleaning, allergy considerations, etc."},
                ]
            }
        ]
    },
    {
        "template_id": "warehouse",
        "name": "Warehouse / Industrial",
        "description": "Heavy-duty cleaning for industrial spaces.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/warehouse_korsp2.jpg",
        "color": "#34495e",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "companyName", "label": "Company name", "type": "text", "placeholder": "ABC Logistics", "required": True},
                    {"id": "contactName", "label": "Contact person", "type": "text", "placeholder": "John Smith, Facility Manager", "required": True},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@company.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Facility address", "type": "textarea", "placeholder": "123 Industrial Pkwy, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "facility-details",
                "title": "Facility Details",
                "description": "Tell us about your facility.",
                "fields": [
                    {"id": "squareFootage", "label": "Total square footage", "type": "number", "placeholder": "50000", "required": True},
                    {"id": "ceilingHeight", "label": "Ceiling height (feet)", "type": "number", "placeholder": "30"},
                    {"id": "floorTypes", "label": "Floor type", "type": "select", "options": ["Sealed concrete", "Epoxy", "Polished concrete", "Industrial tile"], "required": True},
                    {"id": "facilityType", "label": "Facility type", "type": "select", "options": ["Warehouse", "Manufacturing", "Distribution center", "Cold storage", "Mixed use"], "required": True},
                    {"id": "hasOfficeSpace", "label": "Office space included?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "hasLoadingDocks", "label": "Loading docks?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "cleanlinessLevel", "label": "How would you rate the current cleanliness?", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Duty Clean", "Standard Clean", "Light Touch-Up"], "required": True, "hint": "This helps us estimate the time and effort needed"},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Needs",
                "description": "What cleaning services do you need?",
                "fields": [
                    {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["Daily", "Weekly", "Bi-weekly", "Monthly", "Quarterly"], "required": True},
                    {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?"},
                    {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False},
                    {"id": "preferredServiceTime", "label": "Preferred time", "type": "select", "options": ["During operations", "After hours", "Weekends", "24/7 access"], "required": True},
                    {"id": "floorScrubbing", "label": "Floor scrubbing/machine cleaning needed?", "type": "radio", "options": ["Yes", "No"]},
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
                    {"id": "specialRequests", "label": "Any special requests?", "type": "textarea", "placeholder": "High dusting, pressure washing, spill cleanup protocols, etc."},
                ]
            }
        ]
    },
    {
        "template_id": "post-construction",
        "name": "Post-Construction",
        "description": "Deep cleaning after construction or renovation.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/post_construction_uqr9kl.jpg",
        "color": "#f39c12",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True},
                    {"id": "companyName", "label": "Company name (if applicable)", "type": "text", "placeholder": "Smith Construction LLC"},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@email.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Project address", "type": "textarea", "placeholder": "123 New Build St, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "project-details",
                "title": "Project Details",
                "description": "Tell us about the construction project.",
                "fields": [
                    {"id": "squareFootage", "label": "Total square footage", "type": "number", "placeholder": "3000", "required": True},
                    {"id": "projectType", "label": "Project type", "type": "select", "options": ["New construction", "Major renovation", "Minor renovation", "Addition", "Remodel"], "required": True},
                    {"id": "propertyType", "label": "Property type", "type": "select", "options": ["Residential", "Commercial", "Industrial", "Mixed use"], "required": True},
                    {"id": "constructionPhase", "label": "Construction phase", "type": "select", "options": ["Rough clean (during construction)", "Final clean (after completion)", "Touch-up clean (before handover)"], "required": True},
                    {"id": "numberOfFloors", "label": "Number of floors", "type": "number", "placeholder": "2"},
                    {"id": "cleanlinessLevel", "label": "How would you rate the current cleanliness?", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Duty Clean", "Standard Clean", "Light Touch-Up"], "required": True, "hint": "This helps us estimate the time and effort needed"},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Requirements",
                "description": "When and how do you need this service?",
                "fields": [
                    {"id": "cleaningType", "label": "Type of cleaning needed", "type": "select", "options": ["One-time", "Multiple phase cleaning", "Ongoing until completion"], "required": True},
                    {"id": "targetDate", "label": "Target completion date", "type": "date", "required": True, "hint": "When do you need the cleaning completed?"},
                    {"id": "debrisRemoval", "label": "Construction debris removal needed?", "type": "radio", "options": ["Yes", "No"], "required": True},
                    {"id": "windowCleaning", "label": "Window cleaning (interior/exterior)?", "type": "radio", "options": ["Yes, both", "Interior only", "Exterior only", "No"]},
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
                    {"id": "specialRequests", "label": "Any special requests?", "type": "textarea", "placeholder": "Dust removal from HVAC, sticker/label removal, pressure washing, etc."},
                ]
            }
        ]
    },
    {
        "template_id": "move-in-out",
        "name": "Move In / Move Out",
        "description": "Deep cleaning for moving transitions.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087527/Move_in_Move_out_srjbid.webp",
        "color": "#8e44ad",
        "sections": [
            {
                "id": "client-info",
                "title": "Contact Information",
                "description": "Let's start with your details.",
                "fields": [
                    {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True},
                    {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@email.com", "required": True},
                    {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                    {"id": "address", "label": "Property address", "type": "textarea", "placeholder": "123 Main St, Apt 4B, City, State ZIP", "required": True},
                ]
            },
            {
                "id": "move-details",
                "title": "Move Details",
                "description": "Tell us about your move.",
                "fields": [
                    {"id": "moveType", "label": "Type of cleaning", "type": "select", "options": ["Move-out cleaning", "Move-in cleaning", "Both (move-out & move-in)"], "required": True},
                    {"id": "propertyType", "label": "Property type", "type": "select", "options": ["House", "Apartment", "Condo", "Townhouse", "Studio"], "required": True},
                    {"id": "squareFootage", "label": "Approximate square footage", "type": "number", "placeholder": "1500", "required": True},
                    {"id": "bedrooms", "label": "Number of bedrooms", "type": "number", "placeholder": "3", "required": True},
                    {"id": "bathrooms", "label": "Number of bathrooms", "type": "number", "placeholder": "2", "required": True},
                    {"id": "moveDate", "label": "Move date", "type": "date", "required": True, "hint": "When is the move happening?"},
                    {"id": "cleanlinessLevel", "label": "How would you rate the current cleanliness?", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Duty Clean", "Standard Clean", "Light Touch-Up"], "required": True, "hint": "This helps us estimate the time and effort needed"},
                ]
            },
            {
                "id": "property-features",
                "title": "Property Features",
                "description": "Help us understand your space better.",
                "fields": [
                    {"id": "hasGarage", "label": "Garage included?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "hasBasement", "label": "Basement included?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "hasAttic", "label": "Attic access needed?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "hasOutdoorSpace", "label": "Patio/Balcony cleaning needed?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "applianceCleaning", "label": "Appliance cleaning needed?", "type": "checkbox", "options": ["Refrigerator (inside/outside)", "Oven/Stove", "Dishwasher", "Washer/Dryer", "Microwave"]},
                ]
            },
            {
                "id": "service-requirements",
                "title": "Service Needs",
                "description": "What specific services do you need?",
                "fields": [
                    {"id": "preferredDate", "label": "Preferred cleaning date", "type": "date", "required": True},
                    {"id": "preferredTime", "label": "Preferred time", "type": "select", "options": ["Morning (8am-12pm)", "Afternoon (12pm-5pm)", "Flexible"], "required": True},
                    {"id": "windowCleaning", "label": "Window cleaning needed?", "type": "radio", "options": ["Yes, interior only", "Yes, interior & exterior", "No"]},
                    {"id": "carpetCleaning", "label": "Carpet/floor deep cleaning?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "wallCleaning", "label": "Wall washing/spot cleaning?", "type": "radio", "options": ["Yes", "No"]},
                    {"id": "depositReturn", "label": "Is this for a security deposit return?", "type": "radio", "options": ["Yes", "No"], "hint": "We can provide extra attention to landlord inspection areas"},
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
                    {"id": "specialRequests", "label": "Any special requests or areas of concern?", "type": "textarea", "placeholder": "Stubborn stains, pet odors, specific landlord requirements, etc."},
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