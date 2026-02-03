#!/usr/bin/env python3
"""
Environment Variables Validation Script

This script validates that all required environment variables are properly configured.
"""

import os
from pathlib import Path


def check_env_var(name: str, required: bool = True, description: str = "") -> bool:
    """Check if an environment variable is set"""
    value = os.getenv(name)
    status = "✅" if value else ("❌" if required else "⚠️")
    req_text = "Required" if required else "Optional"
    
    if value:
        # Mask sensitive values
        if any(keyword in name.lower() for keyword in ['token', 'secret', 'key', 'password']):
            display_value = f"{'*' * (len(value) - 4)}{value[-4:]}" if len(value) > 4 else "***"
        else:
            display_value = value
        print(f"{status} {name}: {display_value} ({req_text})")
    else:
        print(f"{status} {name}: Not set ({req_text})")
        if description:
            print(f"    {description}")
    
    return bool(value) if required else True


def main():
    print("🔍 Environment Variables Validation")
    print("=" * 50)
    
    # Load .env file if it exists
    env_file = Path(".env")
    if env_file.exists():
        print(f"📁 Loading from: {env_file.absolute()}")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value
        print()
    else:
        print("⚠️  No .env file found. Using system environment variables only.\n")
    
    all_good = True
    
    print("🗄️  Database Configuration:")
    all_good &= check_env_var("DATABASE_URL", True, "PostgreSQL connection string")
    print()
    
    print("🔥 Firebase Configuration:")
    all_good &= check_env_var("FIREBASE_PROJECT_ID", True, "Firebase project identifier")
    print()
    
    print("☁️  Cloudflare R2 Storage:")
    all_good &= check_env_var("R2_ACCOUNT_ID", True)
    all_good &= check_env_var("R2_ACCESS_KEY_ID", True)
    all_good &= check_env_var("R2_SECRET_ACCESS_KEY", True)
    all_good &= check_env_var("R2_BUCKET_NAME", True)
    all_good &= check_env_var("R2_PUBLIC_URL", True)
    print()
    
    print("📧 Email Configuration:")
    all_good &= check_env_var("RESEND_API_KEY", False, "Fallback email service")
    all_good &= check_env_var("EMAIL_FROM_ADDRESS", True)
    all_good &= check_env_var("SMTP_ENCRYPTION_KEY", True, "For custom SMTP encryption")
    print()
    
    print("💳 Payment Configuration:")
    all_good &= check_env_var("DODOPAYMENTS_API_KEY", True)
    all_good &= check_env_var("DODOPAYMENTS_WEBHOOK_SECRET", True)
    print()
    
    print("📅 Calendly Integration:")
    all_good &= check_env_var("CALENDLY_CLIENT_ID", False)
    all_good &= check_env_var("CALENDLY_CLIENT_SECRET", False)
    all_good &= check_env_var("CALENDLY_REDIRECT_URI", False)
    print()
    
    print("🏠 Smarty Address API:")
    smarty_configured = True
    smarty_configured &= check_env_var("SMARTY_AUTH_ID", True, "Get from https://www.smarty.com/")
    smarty_configured &= check_env_var("SMARTY_AUTH_TOKEN", True, "Secret token from Smarty")
    check_env_var("SMARTY_AUTOCOMPLETE_RPM", False, "Rate limit (default: 100)")
    check_env_var("SMARTY_AUTOCOMPLETE_CACHE_SECONDS", False, "Cache duration (default: 3600)")
    print()
    
    print("🌐 Application Configuration:")
    all_good &= check_env_var("FRONTEND_URL", True, "Frontend application URL")
    print()
    
    # Summary
    print("📊 Summary:")
    if all_good:
        print("✅ All required environment variables are configured!")
        if smarty_configured:
            print("✅ Smarty address autocomplete is ready to use")
        print("\n🚀 You can start the application with: python run.py")
    else:
        print("❌ Some required environment variables are missing")
        print("📝 Please check the .env.example file for reference")
        print("🔧 Run this script again after updating your .env file")
    
    if not smarty_configured:
        print("\n🏠 Smarty Setup:")
        print("1. Sign up at https://www.smarty.com/")
        print("2. Get your Auth ID and Auth Token from the dashboard")
        print("3. Add them to your .env file")
        print("4. Run: python setup_smarty.py to test the connection")


if __name__ == "__main__":
    main()