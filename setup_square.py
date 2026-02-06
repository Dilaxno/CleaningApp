"""
Quick Square Setup Script
Helps configure Square integration step by step
"""
import os
from pathlib import Path

def main():
    print("=" * 60)
    print("Square Integration Setup")
    print("=" * 60)
    print()
    
    # Check for .env in root directory (parent of backend)
    backend_dir = Path(__file__).parent
    root_dir = backend_dir.parent
    env_file = root_dir / ".env"
    env_exists = env_file.exists()
    
    if not env_exists:
        print("⚠️  No .env file found in root directory. Creating one...")
        env_file.touch()
    else:
        print(f"✓ Found .env file at: {env_file}")
        print()
    
    print("Please provide your Square credentials:")
    print()
    
    # Get environment
    print("1. Environment (sandbox or production)?")
    environment = input("   Enter 'sandbox' for testing or 'production' for live [sandbox]: ").strip() or "sandbox"
    
    # Get credentials
    print("\n2. Square Application ID")
    print("   (Find this in Square Developer Dashboard > Credentials)")
    app_id = input("   Application ID: ").strip()
    
    print("\n3. Square Application Secret")
    print("   (Find this in Square Developer Dashboard > Credentials)")
    app_secret = input("   Application Secret: ").strip()
    
    print("\n4. Frontend URL")
    print("   (e.g., https://cleanenroll.com or http://localhost:3000)")
    frontend_url = input("   Frontend URL: ").strip()
    
    # Calculate redirect URI
    redirect_uri = f"{frontend_url}/auth/square/callback"
    
    print("\n" + "=" * 60)
    print("Configuration Summary")
    print("=" * 60)
    print(f"Environment: {environment}")
    print(f"Application ID: {app_id[:20]}...")
    print(f"Frontend URL: {frontend_url}")
    print(f"Redirect URI: {redirect_uri}")
    print()
    
    print("⚠️  IMPORTANT: Add this redirect URI to Square Developer Dashboard:")
    print(f"   {redirect_uri}")
    print()
    
    confirm = input("Save this configuration to .env? (y/n): ").strip().lower()
    
    if confirm == 'y':
        # Read existing .env
        existing_content = ""
        if env_exists:
            with open(env_file, 'r') as f:
                existing_content = f.read()
        
        # Remove old Square config if exists
        lines = existing_content.split('\n')
        filtered_lines = [
            line for line in lines 
            if not any(key in line for key in [
                'SQUARE_ENVIRONMENT',
                'SQUARE_APPLICATION_ID',
                'SQUARE_APPLICATION_SECRET',
                'SQUARE_REDIRECT_URI'
            ])
        ]
        
        # Add new Square config
        square_config = f"""
# Square Integration
SQUARE_ENVIRONMENT={environment}
SQUARE_APPLICATION_ID={app_id}
SQUARE_APPLICATION_SECRET={app_secret}
SQUARE_REDIRECT_URI={redirect_uri}
"""
        
        new_content = '\n'.join(filtered_lines).strip() + '\n' + square_config
        
        with open(env_file, 'w') as f:
            f.write(new_content)
        
        print(f"\n✅ Configuration saved to {env_file}")
        print("\nNext steps:")
        print("1. Run database migration: python migrations/run_square_migration.py")
        print("2. Add redirect URI to Square Developer Dashboard")
        print("3. Restart your backend server")
        print("\nSee SQUARE_OAUTH_SETUP.md for detailed instructions")
    else:
        print("\n❌ Configuration not saved")

if __name__ == "__main__":
    main()
