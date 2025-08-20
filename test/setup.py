#!/usr/bin/env python3
"""
Setup script for Freshdesk to JIRA migration tool
"""

import os
import sys
from pathlib import Path

def create_env_file():
    """Create .env file from template"""
    template_path = Path("env_template.txt")
    env_path = Path(".env")
    
    if env_path.exists():
        print("✓ .env file already exists")
        return True
    
    if not template_path.exists():
        print("✗ env_template.txt not found")
        return False
    
    # Copy template to .env
    with open(template_path, 'r') as f:
        content = f.read()
    
    with open(env_path, 'w') as f:
        f.write(content)
    
    print("✓ Created .env file from template")
    print("  Please edit .env file with your JIRA credentials")
    return True

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        'requests',
        'jira',
        'beautifulsoup4',
        'python-dateutil',
        'tqdm',
        'python-dotenv'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} (missing)")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("Install them with: pip install -r requirements.txt")
        return False
    
    return True

def check_data_structure():
    """Check if data structure exists"""
    data_path = Path("../data_to_be_migrated")
    
    if not data_path.exists():
        print("✗ data_to_be_migrated directory not found")
        return False
    
    required_dirs = [
        "ticket_details",
        "conversations", 
        "ticket_attachments",
        "conversation_attachments",
        "user_details",
        "attachments"
    ]
    
    missing_dirs = []
    for dir_name in required_dirs:
        dir_path = data_path / dir_name
        if dir_path.exists():
            print(f"✓ {dir_name}/")
        else:
            print(f"✗ {dir_name}/ (missing)")
            missing_dirs.append(dir_name)
    
    if missing_dirs:
        print(f"\nMissing directories: {', '.join(missing_dirs)}")
        return False
    
    return True

def main():
    """Main setup function"""
    print("=== Freshdesk to JIRA Migration Setup ===\n")
    
    # Check current directory
    if not Path("requirements.txt").exists():
        print("✗ Please run this script from the test/ directory")
        return False
    
    print("1. Checking dependencies...")
    deps_ok = check_dependencies()
    
    print("\n2. Creating environment file...")
    env_ok = create_env_file()
    
    print("\n3. Checking data structure...")
    data_ok = check_data_structure()
    
    print("\n=== Setup Summary ===")
    if deps_ok and env_ok and data_ok:
        print("🎉 Setup completed successfully!")
        print("\nNext steps:")
        print("1. Edit .env file with your JIRA credentials")
        print("2. Run: python scripts/test_migration.py")
        print("3. Run: python scripts/migrate_tickets.py --dry-run --limit 5")
        return True
    else:
        print("⚠️  Setup incomplete. Please fix the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
