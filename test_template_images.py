#!/usr/bin/env python3
"""
Test script to verify all template images are accessible
"""

import asyncio
import httpx

# Template image URLs to test
TEMPLATE_IMAGES = [
    ("Office / Commercial", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/commercial_office_jf1pvb.jpg"),
    ("Retail Store", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/retail_store_h567sp.jpg"),
    ("Medical / Dental Clinic", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/Medical_Clinic_rnq02h.jpg"),
    ("Fitness Gym / Studio", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087510/gym_uhy5i9.jpg"),
    ("Restaurant / Cafe", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087529/cafe_vlqstf.webp"),
    ("Residential / Home", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/residential_aoijhw.jpg"),
    ("Airbnb / Short-Term Rental", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/Airbnb_qopjpn.jpg"),
    ("School / Daycare", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/school_opn4hw.jpg"),
    ("Warehouse / Industrial", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/warehouse_korsp2.jpg"),
    ("Post-Construction", "https://images.unsplash.com/photo-1504307651254-35680f356dfd?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1000&q=80"),
    ("Move In / Move Out", "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087527/Move_in_Move_out_srjbid.webp"),
    ("Deep Clean", "https://images.unsplash.com/photo-1581578731548-c64695cc6952?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1000&q=80"),
]

async def test_template_images():
    """Test that all template images are accessible"""
    
    print("🖼️ Testing Template Images")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        for template_name, image_url in TEMPLATE_IMAGES:
            try:
                print(f"📋 Testing {template_name}...")
                print(f"   URL: {image_url}")
                
                response = await client.head(image_url, timeout=10.0)
                
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "unknown")
                    print(f"   ✅ Image accessible (Content-Type: {content_type})")
                else:
                    print(f"   ❌ Image not accessible (Status: {response.status_code})")
                    
            except Exception as e:
                print(f"   ❌ Error accessing image: {e}")
            
            print()

if __name__ == "__main__":
    asyncio.run(test_template_images())