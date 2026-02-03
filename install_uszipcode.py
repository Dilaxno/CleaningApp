#!/usr/bin/env python3
"""
Install and initialize the uszipcode library.
This script handles the installation and initial database setup.
"""

import subprocess
import sys
import os

def install_uszipcode():
    """Install the uszipcode library."""
    print("📦 Installing uszipcode library...")
    
    try:
        # Install the library
        subprocess.check_call([sys.executable, "-m", "pip", "install", "uszipcode==1.0.1"])
        print("✅ uszipcode library installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install uszipcode: {e}")
        return False

def initialize_database():
    """Initialize the uszipcode database."""
    print("🗄️ Initializing ZIP code database...")
    
    try:
        from uszipcode import SearchEngine
        
        # Create search engine (this will download and initialize the database)
        search = SearchEngine()
        
        # Test with a known ZIP code
        test_zip = search.by_zipcode("90210")
        
        if test_zip and test_zip.zipcode:
            print(f"✅ Database initialized successfully")
            print(f"   Test lookup: {test_zip.zipcode} -> {test_zip.major_city}, {test_zip.state}")
            return True
        else:
            print("❌ Database initialization failed - test lookup returned no results")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import uszipcode: {e}")
        return False
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

def verify_installation():
    """Verify the installation is working correctly."""
    print("🧪 Verifying installation...")
    
    try:
        from uszipcode import SearchEngine
        
        search = SearchEngine()
        
        # Test multiple ZIP codes
        test_cases = [
            ("90210", "Beverly Hills", "CA"),
            ("10001", "New York", "NY"),
            ("60601", "Chicago", "IL"),
        ]
        
        for zipcode, expected_city, expected_state in test_cases:
            zip_info = search.by_zipcode(zipcode)
            
            if zip_info and zip_info.zipcode:
                city = zip_info.major_city or zip_info.post_office_city
                state = zip_info.state
                
                if expected_state.upper() == state.upper():
                    print(f"✅ {zipcode}: {city}, {state}")
                else:
                    print(f"❌ {zipcode}: Expected {expected_state}, got {state}")
                    return False
            else:
                print(f"❌ {zipcode}: No data found")
                return False
        
        print("✅ Installation verification completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def main():
    """Main installation process."""
    print("🚀 uszipcode Library Installation")
    print("=" * 40)
    
    success = True
    
    # Step 1: Install library
    if not install_uszipcode():
        success = False
    
    # Step 2: Initialize database
    if success and not initialize_database():
        success = False
    
    # Step 3: Verify installation
    if success and not verify_installation():
        success = False
    
    print("\n" + "=" * 40)
    
    if success:
        print("🎉 uszipcode installation completed successfully!")
        print("\n📋 Next steps:")
        print("1. Restart your FastAPI application")
        print("2. Test the service area validation endpoints")
        print("3. The ZIP code database is now ready for production use")
        
        print("\n📊 Database info:")
        try:
            from uszipcode import SearchEngine
            search = SearchEngine()
            print(f"• Database path: {search.db_file_path}")
            print(f"• Total ZIP codes: ~40,000+ US ZIP codes")
            print(f"• Data includes: ZIP, city, county, state, coordinates")
        except:
            pass
            
    else:
        print("❌ Installation failed. Please check the errors above.")
        print("\n🔧 Troubleshooting:")
        print("• Ensure you have internet connection for initial download")
        print("• Check that you have write permissions in the Python environment")
        print("• Try running with elevated permissions if needed")
        sys.exit(1)

if __name__ == "__main__":
    main()