#!/usr/bin/env python3
"""
Install and test the zipcodes library.
This script handles the installation and testing.
"""

import subprocess
import sys
import os

def install_zipcodes():
    """Install the zipcodes library."""
    print("📦 Installing zipcodes library...")
    
    try:
        # Install the library
        subprocess.check_call([sys.executable, "-m", "pip", "install", "zipcodes==1.2.0"])
        print("✅ zipcodes library installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install zipcodes: {e}")
        return False

def test_installation():
    """Test the zipcodes library installation."""
    print("🧪 Testing zipcodes library...")
    
    try:
        import zipcodes
        
        # Test with a known ZIP code
        test_zip = zipcodes.matching("90210")
        
        if test_zip and len(test_zip) > 0:
            zip_data = test_zip[0]
            city = zip_data.get('city', 'Unknown')
            state = zip_data.get('state', 'Unknown')
            county = zip_data.get('county', 'Unknown')
            
            print(f"✅ Library working correctly")
            print(f"   Test lookup: 90210 -> {city}, {county}, {state}")
            return True
        else:
            print("❌ Library test failed - no data returned")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import zipcodes: {e}")
        return False
    except Exception as e:
        print(f"❌ Library test failed: {e}")
        return False

def verify_performance():
    """Verify the library performance."""
    print("⚡ Testing performance...")
    
    try:
        import zipcodes
        import time
        
        # Test multiple ZIP codes
        test_zips = ["90210", "10001", "60601", "77001", "33101"]
        
        start_time = time.time()
        
        for zipcode in test_zips:
            result = zipcodes.matching(zipcode)
        
        end_time = time.time()
        total_time = (end_time - start_time) * 1000  # Convert to milliseconds
        avg_time = total_time / len(test_zips)
        
        print(f"✅ Performance test completed")
        print(f"   Average lookup time: {avg_time:.2f}ms per ZIP code")
        
        if avg_time < 1:
            print("🚀 Performance: Excellent (< 1ms per lookup)")
        elif avg_time < 10:
            print("✅ Performance: Good (< 10ms per lookup)")
        else:
            print("⚠️ Performance: Acceptable but could be optimized")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False

def main():
    """Main installation and testing process."""
    print("🚀 zipcodes Library Installation & Testing")
    print("=" * 45)
    
    success = True
    
    # Step 1: Install library
    if not install_zipcodes():
        success = False
    
    # Step 2: Test installation
    if success and not test_installation():
        success = False
    
    # Step 3: Verify performance
    if success and not verify_performance():
        success = False
    
    print("\n" + "=" * 45)
    
    if success:
        print("🎉 zipcodes library installation completed successfully!")
        print("\n📋 Next steps:")
        print("1. Restart your FastAPI application")
        print("2. Test the service area validation endpoints")
        print("3. The ZIP code validation is now ready for production use")
        
        print("\n📊 Library advantages:")
        print("• ✅ Lightweight and fast (in-memory data)")
        print("• ✅ No external database files required")
        print("• ✅ No SQLAlchemy compatibility issues")
        print("• ✅ Simple API with multiple lookup methods")
        print("• ✅ Comprehensive US ZIP code coverage")
        print("• ✅ Battle-tested and reliable")
            
    else:
        print("❌ Installation failed. Please check the errors above.")
        print("\n🔧 Troubleshooting:")
        print("• Ensure you have internet connection")
        print("• Check that you have write permissions in the Python environment")
        print("• Try running: pip install zipcodes")
        sys.exit(1)

if __name__ == "__main__":
    main()