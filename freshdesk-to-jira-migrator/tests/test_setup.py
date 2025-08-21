#!/usr/bin/env python3
"""
Test script to verify the project setup and configuration.
"""

import sys
import json
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from core.field_mapper import FieldMapper
from core.data_loader import DataLoader
from config.mapper_functions import MAPPER_FUNCTIONS


def test_field_mapper():
    """Test field mapper functionality."""
    print("🔍 Testing Field Mapper...")
    
    try:
        mapper = FieldMapper()
        mapping = mapper.get_all_mapped_fields()
        
        print(f"✅ Field mapper loaded successfully")
        print(f"   - Ticket fields: {len(mapping.get('ticket_fields', {}))}")
        print(f"   - Conversation fields: {len(mapping.get('conversation_fields', {}))}")
        print(f"   - Attachment fields: {len(mapping.get('attachment_fields', {}))}")
        print(f"   - User fields: {len(mapping.get('user_fields', {}))}")
        
        return True
    except Exception as e:
        print(f"❌ Field mapper test failed: {e}")
        return False


def test_mapper_functions():
    """Test mapper functions."""
    print("\n🔍 Testing Mapper Functions...")
    
    try:
        print(f"✅ Mapper functions loaded successfully")
        print(f"   - Available functions: {list(MAPPER_FUNCTIONS.keys())}")
        
        # Test a few functions
        from config.mapper_functions import map_priority, extract_emails, format_date
        
        # Test priority mapping
        assert map_priority(1) == "Low"
        assert map_priority(3) == "High"
        print("   - Priority mapping: ✅")
        
        # Test email extraction
        emails = extract_emails(["test@example.com", "'Name' <name@example.com>"])
        assert "test@example.com" in emails
        assert "name@example.com" in emails
        print("   - Email extraction: ✅")
        
        # Test date formatting
        formatted_date = format_date("2024-01-15T10:30:00Z")
        assert formatted_date == "2024-01-15"
        print("   - Date formatting: ✅")
        
        return True
    except Exception as e:
        print(f"❌ Mapper functions test failed: {e}")
        return False


def test_data_loader():
    """Test data loader functionality."""
    print("\n🔍 Testing Data Loader...")
    
    try:
        loader = DataLoader()
        
        # Test data directory validation
        is_valid = loader.validate_data_directory()
        print(f"   - Data directory validation: {'✅' if is_valid else '❌'}")
        
        # Get data summary
        summary = loader.get_data_summary()
        print(f"   - Total tickets available: {summary['total_tickets']}")
        print(f"   - Data directory: {summary['data_directory']}")
        
        return True
    except Exception as e:
        print(f"❌ Data loader test failed: {e}")
        return False


def test_configuration_files():
    """Test configuration files."""
    print("\n🔍 Testing Configuration Files...")
    
    config_dir = Path(__file__).parent.parent / "config"
    
    # Test field mapping file
    field_mapping_file = config_dir / "field_mapping.json"
    if field_mapping_file.exists():
        with open(field_mapping_file, 'r') as f:
            mapping = json.load(f)
        print(f"   - Field mapping file: ✅ ({len(mapping)} categories)")
    else:
        print(f"   - Field mapping file: ❌ (not found)")
        return False
    
    # Test custom fields file
    custom_fields_file = config_dir / "jira_custom_fields.json"
    if custom_fields_file.exists():
        with open(custom_fields_file, 'r') as f:
            custom_fields = json.load(f)
        print(f"   - Custom fields file: ✅ ({len(custom_fields.get('custom_fields', {}))} fields)")
    else:
        print(f"   - Custom fields file: ❌ (not found)")
        return False
    
    # Test mapper functions file
    mapper_functions_file = config_dir / "mapper_functions.py"
    if mapper_functions_file.exists():
        print(f"   - Mapper functions file: ✅")
    else:
        print(f"   - Mapper functions file: ❌ (not found)")
        return False
    
    return True


def main():
    """Run all tests."""
    print("🧪 Running Freshdesk to JIRA Migrator Setup Tests\n")
    
    tests = [
        test_configuration_files,
        test_field_mapper,
        test_mapper_functions,
        test_data_loader
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The setup is ready for migration.")
        return 0
    else:
        print("❌ Some tests failed. Please check the configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
