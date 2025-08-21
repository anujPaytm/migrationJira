#!/usr/bin/env python3
"""
Test script to verify the new configuration works with actual data.
"""

import sys
import json
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from core.data_loader import DataLoader
from core.field_mapper import FieldMapper
from core.ticket_converter import TicketConverter


def test_ticket_52_mapping():
    """Test the mapping logic with ticket 52."""
    print("🧪 Testing Ticket 52 Mapping\n")
    
    # Initialize components
    data_loader = DataLoader()
    field_mapper = FieldMapper()
    ticket_converter = TicketConverter(field_mapper)
    
    # Load ticket 52 data
    ticket_data = data_loader.load_ticket_data(52)
    
    if not ticket_data['ticket_details']:
        print("❌ Could not load ticket 52 details")
        return False
    
    print("✅ Loaded ticket 52 data")
    print(f"   - Ticket ID: {ticket_data['ticket_id']}")
    print(f"   - Conversations: {len(ticket_data['conversations'])}")
    print(f"   - Ticket attachments: {len(ticket_data['ticket_attachments'])}")
    print(f"   - Conversation attachments: {len(ticket_data['conversation_attachments'])}")
    print(f"   - User data: {len(ticket_data['user_data'].get('agents', {}))} agents, {len(ticket_data['user_data'].get('contacts', {}))} contacts")
    
    # Test field mapping
    ticket_details = ticket_data['ticket_details']
    mapped_fields, unmapped_fields = field_mapper.map_ticket_fields(ticket_details, ticket_data['user_data'])
    
    print(f"\n📊 Field Mapping Results:")
    print(f"   - Mapped fields: {list(mapped_fields.keys())}")
    print(f"   - Unmapped fields: {list(unmapped_fields.keys())}")
    print(f"   - Mapping coverage: {len(mapped_fields)}/{len(ticket_details)} ({len(mapped_fields)/len(ticket_details)*100:.1f}%)")
    
    # Show mapped field values
    print(f"\n🔗 Mapped Field Values:")
    for field_name, field_value in mapped_fields.items():
        print(f"   - {field_name}: {field_value}")
    
    # Show some unmapped fields
    print(f"\n📝 Sample Unmapped Fields (will go to description):")
    for i, (field_name, field_value) in enumerate(unmapped_fields.items()):
        if i < 5:  # Show first 5
            print(f"   - {field_name}: {field_value}")
        else:
            break
    
    # Test full conversion
    print(f"\n🔄 Testing Full Conversion...")
    jira_issue = ticket_converter.convert_to_jira_issue(
        ticket=ticket_details,
        conversations=ticket_data['conversations'],
        ticket_attachments=ticket_data['ticket_attachments'],
        conversation_attachments=ticket_data['conversation_attachments'],
        user_data=ticket_data['user_data']
    )
    
    print(f"✅ Conversion completed")
    print(f"   - JIRA fields: {list(jira_issue['fields'].keys())}")
    
    # Show the mapped custom fields
    custom_fields = {k: v for k, v in jira_issue['fields'].items() if k.startswith('FD_')}
    print(f"\n🎯 Mapped Custom Fields:")
    for field_name, field_value in custom_fields.items():
        print(f"   - {field_name}: {field_value}")
    
    # Show description length
    description = jira_issue['fields'].get('description', '')
    print(f"\n📄 Description:")
    print(f"   - Length: {len(description)} characters")
    print(f"   - Preview: {description[:200]}...")
    
    return True


def test_user_mapping():
    """Test user ID mapping functionality."""
    print("\n🧪 Testing User ID Mapping\n")
    
    data_loader = DataLoader()
    field_mapper = FieldMapper()
    
    # Load ticket 52 to get user IDs
    ticket_data = data_loader.load_ticket_data(52)
    ticket_details = ticket_data['ticket_details']
    
    if not ticket_details:
        print("❌ Could not load ticket details")
        return False
    
    requester_id = ticket_details.get('requester_id')
    responder_id = ticket_details.get('responder_id')
    
    print(f"📋 User IDs from ticket:")
    print(f"   - Requester ID: {requester_id}")
    print(f"   - Responder ID: {responder_id}")
    
    # Test user mapping
    if requester_id:
        jira_field, mapped_value = field_mapper.map_field_value(
            'requester_id', requester_id, 'ticket_fields', ticket_data['user_data']
        )
        print(f"   - Requester mapping: {jira_field} = {mapped_value}")
    
    if responder_id:
        jira_field, mapped_value = field_mapper.map_field_value(
            'responder_id', responder_id, 'ticket_fields', ticket_data['user_data']
        )
        print(f"   - Responder mapping: {jira_field} = {mapped_value}")
    
    return True


def main():
    """Run all tests."""
    print("🚀 Freshdesk to JIRA Migrator - Configuration Test\n")
    
    tests = [
        test_ticket_52_mapping,
        test_user_mapping
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The configuration is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
