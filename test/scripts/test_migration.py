#!/usr/bin/env python3
"""
Test script for Freshdesk to JIRA migration
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.jira_config import JiraConfig
from utils.data_loader import DataLoader
from utils.user_mapper import UserMapper
from utils.ticket_converter import TicketConverter

def test_configuration():
    """Test JIRA configuration"""
    print("Testing JIRA configuration...")
    try:
        config = JiraConfig()
        config.validate()
        print("✓ Configuration is valid")
        print(f"  - Domain: {config.domain}")
        print(f"  - Project: {config.project_key}")
        print(f"  - Dry Run: {config.dry_run}")
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False

def test_jira_connection():
    """Test JIRA connection"""
    print("\nTesting JIRA connection...")
    try:
        from jira import JIRA
        config = JiraConfig()
        
        jira = JIRA(
            options=config.get_jira_options(),
            basic_auth=config.get_auth()
        )
        
        # Test connection by getting project info
        project = jira.project(config.project_key)
        print(f"✓ Connected to JIRA successfully")
        print(f"  - Project: {project.name} ({project.key})")
        return True
    except Exception as e:
        print(f"✗ JIRA connection failed: {e}")
        return False

def test_data_loading():
    """Test data loading"""
    print("\nTesting data loading...")
    try:
        data_loader = DataLoader()
        
        # Test loading users
        users = data_loader.load_users()
        agent_count = len(users.get('agents', []))
        contact_count = len(users.get('contacts', []))
        print(f"✓ Loaded {agent_count} agents and {contact_count} contacts")
        
        # Test loading ticket details
        tickets = data_loader.load_ticket_details()
        print(f"✓ Loaded {len(tickets)} ticket details")
        
        # Test loading conversations
        conversations = data_loader.load_conversations()
        print(f"✓ Loaded conversations for {len(conversations)} tickets")
        
        # Test loading attachments
        ticket_attachments = data_loader.load_ticket_attachments()
        print(f"✓ Loaded ticket attachments for {len(ticket_attachments)} tickets")
        
        return True
    except Exception as e:
        print(f"✗ Data loading failed: {e}")
        return False

def test_user_mapping():
    """Test user mapping"""
    print("\nTesting user mapping...")
    try:
        data_loader = DataLoader()
        users_data = data_loader.load_users()
        user_mapper = UserMapper(users_data)
        
        # Test with a sample ticket
        sample_ticket = data_loader.load_ticket_details(52)
        if sample_ticket:
            requester_id = sample_ticket.get('requester_id')
            responder_id = sample_ticket.get('responder_id')
            
            requester = user_mapper.get_requester_info(requester_id)
            responder = user_mapper.get_responder_info(responder_id)
            
            print(f"✓ User mapping working")
            if requester:
                print(f"  - Requester: {requester.get('name')} ({requester.get('email')})")
            if responder:
                print(f"  - Responder: {responder.get('name')} ({responder.get('email')})")
        
        return True
    except Exception as e:
        print(f"✗ User mapping failed: {e}")
        return False

def test_ticket_conversion():
    """Test ticket conversion"""
    print("\nTesting ticket conversion...")
    try:
        data_loader = DataLoader()
        users_data = data_loader.load_users()
        user_mapper = UserMapper(users_data)
        ticket_converter = TicketConverter(user_mapper)
        
        # Test with sample ticket
        sample_ticket = data_loader.load_ticket_details(52)
        if sample_ticket:
            conversations = data_loader.load_conversations(52).get(52, [])
            
            jira_issue = ticket_converter.convert_to_jira_issue(sample_ticket, conversations)
            
            print("✓ Ticket conversion working")
            print(f"  - Summary: {jira_issue['fields']['summary']}")
            print(f"  - Priority: {jira_issue['fields']['priority']['name']}")
            print(f"  - Labels: {jira_issue['fields']['labels']}")
            
            # Show description preview
            description = jira_issue['fields']['description']
            preview = description[:200] + "..." if len(description) > 200 else description
            print(f"  - Description preview: {preview}")
        
        return True
    except Exception as e:
        print(f"✗ Ticket conversion failed: {e}")
        return False

def test_sample_migration():
    """Test sample migration with ticket 52"""
    print("\nTesting sample migration (ticket 52)...")
    try:
        from scripts.migrate_tickets import TicketMigrator
        
        migrator = TicketMigrator()
        
        # Test in dry-run mode
        success = migrator.migrate_single_ticket(52)
        
        if success:
            print("✓ Sample migration test completed successfully")
        else:
            print("✗ Sample migration test failed")
        
        return success
    except Exception as e:
        print(f"✗ Sample migration test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=== Freshdesk to JIRA Migration Test Suite ===\n")
    
    tests = [
        ("Configuration", test_configuration),
        ("JIRA Connection", test_jira_connection),
        ("Data Loading", test_data_loading),
        ("User Mapping", test_user_mapping),
        ("Ticket Conversion", test_ticket_conversion),
        ("Sample Migration", test_sample_migration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ {test_name} test failed with exception: {e}")
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    if passed == total:
        print("🎉 All tests passed! Migration setup is ready.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    main()
