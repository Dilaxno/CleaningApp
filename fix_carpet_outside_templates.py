"""
Fix carpet-cleaning and outside-cleaning templates by adding proper template_data
"""
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

# Template data for outside-cleaning
outside_cleaning_data = {
    "sections": [
        {
            "id": "client-info",
            "title": "Contact Information",
            "description": "Let's start with your details.",
            "fields": [
                {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True},
                {"id": "companyName", "label": "Company/Property name", "type": "text", "placeholder": "Smith Properties LLC"},
                {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@email.com", "required": True},
                {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                {"id": "address", "label": "Property address", "type": "textarea", "placeholder": "123 Main St, City, State ZIP", "required": True}
            ]
        },
        {
            "id": "property-details",
            "title": "Property Details",
            "description": "Tell us about your exterior space.",
            "fields": [
                {"id": "propertyType", "label": "Property type", "type": "select", "options": ["Residential Home", "Commercial Building", "Office Complex", "Retail Store", "Restaurant", "Warehouse", "Multi-unit Building", "Other"], "required": True},
                {"id": "buildingStories", "label": "Number of stories", "type": "number", "placeholder": "2", "required": True},
                {"id": "exteriorMaterial", "label": "Primary exterior material", "type": "select", "options": ["Brick", "Vinyl Siding", "Wood Siding", "Stucco", "Metal", "Stone", "Mixed Materials"], "required": True},
                {"id": "roofType", "label": "Roof type", "type": "select", "options": ["Shingle", "Metal", "Tile", "Flat", "Other"], "required": False},
                {"id": "hasGutters", "label": "Gutters present?", "type": "radio", "options": ["Yes", "No"], "required": True},
                {"id": "windowCount", "label": "Approximate number of exterior windows", "type": "number", "placeholder": "20", "required": True},
                {"id": "hasPatioDecks", "label": "Patios, decks, or outdoor areas?", "type": "radio", "options": ["Yes", "No"], "required": True},
                {"id": "hasDriveway", "label": "Driveway or walkways?", "type": "radio", "options": ["Yes", "No"], "required": True},
                {"id": "cleanlinessLevel", "label": "Current exterior condition", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["https://res.cloudinary.com/dxqum9ywx/image/upload/v1770252734/Heavy_duty_clean_z58dty.svg", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1770252734/standard_clean_q0m5fm.svg", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1770252734/light_touch_up_gsb0ho.svg"], "required": True, "hint": "This helps us estimate the time and effort needed"}
            ]
        },
        {
            "id": "service-requirements",
            "title": "Exterior Cleaning Services",
            "description": "What exterior cleaning services do you need?",
            "fields": [
                {"id": "cleaningFrequency", "label": "How often do you need exterior cleaning?", "type": "select", "options": ["One-time", "Quarterly", "Bi-annually", "Annually", "As needed"], "required": True},
                {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?"},
                {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False},
                {"id": "servicesNeeded", "label": "Services needed", "type": "checkbox", "options": ["Pressure washing exterior walls", "Window cleaning (exterior)", "Gutter cleaning", "Roof cleaning", "Driveway/walkway cleaning", "Deck/patio cleaning", "Awning cleaning", "Signage cleaning"], "required": True, "hint": "Select all services you need"},
                {"id": "pressureWashingAreas", "label": "Specific pressure washing areas", "type": "textarea", "placeholder": "Building exterior, sidewalks, parking areas, loading docks, etc.", "required": False},
                {"id": "windowCleaningFloors", "label": "Window cleaning - which floors?", "type": "select", "options": ["Ground floor only", "All floors", "Specific floors"], "required": False},
                {"id": "gutterCondition", "label": "Gutter condition", "type": "select", "options": ["Clean, just maintenance", "Moderately clogged", "Heavily clogged", "Not sure"], "required": False},
                {"id": "seasonalTiming", "label": "Preferred season/timing", "type": "select", "options": ["Spring cleaning", "Summer maintenance", "Fall preparation", "Winter touch-up", "Flexible"], "required": True},
                {"id": "weatherRestrictions", "label": "Weather considerations", "type": "textarea", "placeholder": "Any weather-related restrictions or preferences", "required": False},
                {"id": "accessEquipment", "label": "Special access needed?", "type": "radio", "options": ["Standard equipment sufficient", "High-reach equipment needed", "Ladder access required", "Not sure"], "required": True, "hint": "For multi-story buildings or hard-to-reach areas"},
                {"id": "selectedPackage", "label": "Choose your service package", "type": "packages", "required": False, "hint": "Select a service package that best fits your needs"},
                {"id": "selectedAddons", "label": "Additional services", "type": "addons", "required": False, "hint": "Select any additional services you'd like"},
                {"id": "propertyShots", "label": "Property photos", "type": "file", "required": True, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload exterior photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business. Minimum 2 photos, maximum 10 photos, 50MB per image."},
                {"id": "specialRequests", "label": "Special requests or concerns", "type": "textarea", "placeholder": "Delicate surfaces, landscaping protection, specific cleaning products, timing constraints, etc.", "required": False}
            ]
        }
    ]
}

# Template data for carpet-cleaning
carpet_cleaning_data = {
    "sections": [
        {
            "id": "client-info",
            "title": "Contact Information",
            "description": "Let's start with your details.",
            "fields": [
                {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True},
                {"id": "companyName", "label": "Company name (if commercial)", "type": "text", "placeholder": "Smith Office Building"},
                {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@email.com", "required": True},
                {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True},
                {"id": "address", "label": "Property address", "type": "textarea", "placeholder": "123 Main St, City, State ZIP", "required": True}
            ]
        },
        {
            "id": "carpet-details",
            "title": "Carpet & Upholstery Details",
            "description": "Tell us about your carpets and furniture.",
            "fields": [
                {"id": "propertyType", "label": "Property type", "type": "select", "options": ["Residential Home", "Office/Commercial", "Restaurant", "Hotel", "Medical Facility", "Retail Store", "Other"], "required": True},
                {"id": "totalCarpetArea", "label": "Total carpet area (sq ft)", "type": "number", "placeholder": "800", "required": True},
                {"id": "carpetType", "label": "Primary carpet type", "type": "select", "options": ["Low pile", "Medium pile", "High pile/Shag", "Berber", "Oriental/Persian", "Mixed types", "Not sure"], "required": True},
                {"id": "carpetAge", "label": "Carpet age", "type": "select", "options": ["Less than 1 year", "1-3 years", "3-5 years", "5-10 years", "Over 10 years", "Not sure"], "required": True},
                {"id": "roomsWithCarpet", "label": "Rooms with carpet", "type": "checkbox", "options": ["Living room", "Bedrooms", "Dining room", "Hallways", "Stairs", "Office areas", "Conference rooms", "Reception area", "Other"], "required": True},
                {"id": "upholsteryItems", "label": "Upholstery items to clean", "type": "checkbox", "options": ["Sofa/Couch", "Armchairs", "Dining chairs", "Office chairs", "Ottomans", "Mattresses", "Curtains/Drapes", "None"], "required": False},
                {"id": "upholsteryFabric", "label": "Upholstery fabric type", "type": "select", "options": ["Cotton", "Leather", "Microfiber", "Velvet", "Linen", "Synthetic blend", "Mixed fabrics", "Not sure"], "required": False},
                {"id": "lastCleaning", "label": "Last professional cleaning", "type": "select", "options": ["Never", "Over 2 years ago", "1-2 years ago", "6-12 months ago", "3-6 months ago", "Less than 3 months ago"], "required": True},
                {"id": "carpetCondition", "label": "Current carpet condition", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["https://res.cloudinary.com/dxqum9ywx/image/upload/v1770252734/Heavy_duty_clean_z58dty.svg", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1770252734/standard_clean_q0m5fm.svg", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1770252734/light_touch_up_gsb0ho.svg"], "required": True, "hint": "This helps us estimate the time and effort needed"}
            ]
        },
        {
            "id": "service-requirements",
            "title": "Cleaning Service Details",
            "description": "What carpet cleaning services do you need?",
            "fields": [
                {"id": "cleaningMethod", "label": "Preferred cleaning method", "type": "select", "options": ["Steam cleaning (hot water extraction)", "Dry cleaning", "Shampooing", "Bonnet cleaning", "Professional recommendation"], "required": True, "hint": "Steam cleaning is most common and effective for deep cleaning"},
                {"id": "cleaningFrequency", "label": "How often do you need carpet cleaning?", "type": "select", "options": ["One-time", "Every 6 months", "Annually", "Every 2 years", "As needed"], "required": True},
                {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?"},
                {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False},
                {"id": "stainTypes", "label": "Types of stains present", "type": "checkbox", "options": ["Pet stains/odors", "Food/beverage spills", "Mud/dirt", "Grease/oil", "Ink", "Blood", "Wine", "General wear patterns", "No specific stains"], "required": True},
                {"id": "petOdorTreatment", "label": "Pet odor treatment needed?", "type": "radio", "options": ["Yes - Strong odors", "Yes - Mild odors", "No pets/odors"], "required": True},
                {"id": "stainProtection", "label": "Stain protection application?", "type": "radio", "options": ["Yes", "No", "Undecided"], "required": True, "hint": "Protective coating to help prevent future stains"},
                {"id": "dryingTime", "label": "Drying time preference", "type": "select", "options": ["Standard (4-6 hours)", "Fast dry (2-4 hours)", "Overnight acceptable", "No preference"], "required": True},
                {"id": "accessTime", "label": "Property access time", "type": "select", "options": ["Morning (8am-12pm)", "Afternoon (12pm-5pm)", "Evening (5pm-8pm)", "Flexible"], "required": True},
                {"id": "moveFurniture", "label": "Furniture moving needed?", "type": "radio", "options": ["Yes - move all furniture", "Yes - light furniture only", "No - work around furniture"], "required": True},
                {"id": "preVacuuming", "label": "Pre-vacuuming service?", "type": "radio", "options": ["Yes - include vacuuming", "No - already vacuumed", "No - will vacuum myself"], "required": True},
                {"id": "selectedPackage", "label": "Choose your service package", "type": "packages", "required": False, "hint": "Select a service package that best fits your needs"},
                {"id": "selectedAddons", "label": "Additional services", "type": "addons", "required": False, "hint": "Select any additional services you'd like"},
                {"id": "propertyShots", "label": "Carpet & upholstery photos", "type": "file", "required": True, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos of carpets and upholstery to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business. Minimum 2 photos, maximum 10 photos, 50MB per image."},
                {"id": "specialRequests", "label": "Special requests or concerns", "type": "textarea", "placeholder": "Eco-friendly products, allergies, delicate fabrics, specific stain concerns, timing constraints, etc.", "required": False}
            ]
        }
    ]
}

def run_fix():
    print("Fixing carpet-cleaning and outside-cleaning templates...")
    print("="*80)
    
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Update outside-cleaning template
        print("\n1️⃣ Updating 'outside-cleaning' template with proper data...")
        db.execute(text("""
            UPDATE form_templates
            SET template_data = :template_data
            WHERE template_id = 'outside-cleaning'
        """), {"template_data": json.dumps(outside_cleaning_data)})
        db.commit()
        print("   ✅ Successfully updated 'outside-cleaning'")
        
        # Update carpet-cleaning template
        print("\n2️⃣ Updating 'carpet-cleaning' template with proper data...")
        db.execute(text("""
            UPDATE form_templates
            SET template_data = :template_data
            WHERE template_id = 'carpet-cleaning'
        """), {"template_data": json.dumps(carpet_cleaning_data)})
        db.commit()
        print("   ✅ Successfully updated 'carpet-cleaning'")
        
        print(f"\n{'='*80}")
        print("✅ Template fix completed successfully!")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_fix()
