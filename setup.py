#!/usr/bin/env python3
"""
Quick start setup script for Social Media Scraping API.

This script helps new users get the API up and running quickly by:
- Validating environment configuration
- Testing database connectivity
- Creating initial admin user (optional)
- Running basic system checks

Usage:
    python setup.py            # Interactive setup
    python setup.py --check    # Just run system checks
    python setup.py --admin    # Create admin user
"""

import os
import sys
import asyncio
import getpass
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def print_header():
    """Print setup script header."""
    print("=" * 60)
    print("🚀 Social Media Scraping API - Quick Setup")
    print("=" * 60)
    print()

def check_environment():
    """Check if environment variables are properly configured."""
    print("📋 Checking Environment Configuration...")
    
    required_vars = [
        "DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD",
        "SECRET_KEY", "INSTAGRAM_USERNAME", "INSTAGRAM_PASSWORD", "API_KEY"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Please update your .env file with the missing variables.")
        return False
    else:
        print("✅ All required environment variables are set.")
        return True

def test_database():
    """Test database connectivity."""
    print("\n🗄️  Testing Database Connection...")
    
    try:
        from app.database import test_connection
        if test_connection():
            print("✅ Database connection successful.")
            return True
        else:
            print("❌ Database connection failed.")
            return False
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def create_tables():
    """Create database tables."""
    print("\n📊 Creating Database Tables...")
    
    try:
        from app.database import create_tables as db_create_tables
        db_create_tables()
        print("✅ Database tables created successfully.")
        return True
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        return False

def create_admin_user():
    """Create an admin user interactively."""
    print("\n👤 Creating Admin User...")
    
    try:
        # Import here to avoid import issues if DB isn't ready
        from app.database import SessionLocal
        from app.models import User
        from app.auth.auth import get_password_hash
        
        # Get user input
        username = input("Enter admin username: ").strip()
        if not username:
            print("❌ Username cannot be empty.")
            return False
            
        email = input("Enter admin email: ").strip()
        if not email or "@" not in email:
            print("❌ Please enter a valid email address.")
            return False
            
        password = getpass.getpass("Enter admin password: ")
        if len(password) < 8:
            print("❌ Password must be at least 8 characters long.")
            return False
        
        confirm_password = getpass.getpass("Confirm admin password: ")
        if password != confirm_password:
            print("❌ Passwords do not match.")
            return False
        
        # Create user in database
        db = SessionLocal()
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                print("❌ User with this username or email already exists.")
                return False
            
            # Create new admin user
            hashed_password = get_password_hash(password)
            admin_user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                is_active=True,
                is_admin=True
            )
            
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            print(f"✅ Admin user '{username}' created successfully.")
            print(f"📧 Email: {email}")
            print(f"🆔 User ID: {admin_user.id}")
            return True
            
        except Exception as e:
            db.rollback()
            print(f"❌ Failed to create admin user: {e}")
            return False
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        return False

def test_api_startup():
    """Test if the API can start properly."""
    print("\n🔧 Testing API Startup...")
    
    try:
        from app.main import app
        print("✅ API application imported successfully.")
        
        # Test if we can create the FastAPI app
        if hasattr(app, 'openapi'):
            print("✅ FastAPI application is properly configured.")
            return True
        else:
            print("❌ FastAPI application configuration issue.")
            return False
            
    except Exception as e:
        print(f"❌ API startup test failed: {e}")
        return False

def run_system_checks():
    """Run all system checks."""
    print_header()
    
    checks = [
        ("Environment Configuration", check_environment),
        ("Database Connection", test_database),
        ("Database Tables", create_tables),
        ("API Startup", test_api_startup)
    ]
    
    results = {}
    for name, check_func in checks:
        results[name] = check_func()
    
    print("\n" + "=" * 60)
    print("📋 System Check Summary:")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:.<30} {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All system checks passed! Your API is ready to run.")
        print("\n🚀 To start the API:")
        print("   Development: python run.py")
        print("   Production:  python run.py --production")
        print("\n📚 API Documentation will be available at:")
        print("   http://localhost:8000/docs")
        
    else:
        print("\n⚠️  Some checks failed. Please resolve the issues above before running the API.")
    
    return all_passed

def main():
    """Main setup function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Social Media Scraping API Setup")
    parser.add_argument("--check", action="store_true", help="Run system checks only")
    parser.add_argument("--admin", action="store_true", help="Create admin user")
    
    args = parser.parse_args()
    
    if args.check:
        run_system_checks()
    elif args.admin:
        print_header()
        if not check_environment():
            return
        if not test_database():
            return
        create_admin_user()
    else:
        # Interactive setup
        if run_system_checks():
            print("\n" + "=" * 60)
            create_admin = input("\n🤔 Would you like to create an admin user? (y/N): ").lower()
            if create_admin in ['y', 'yes']:
                create_admin_user()
            
            print("\n🎯 Setup complete! You can now start the API.")

if __name__ == "__main__":
    main()