#!/usr/bin/env python3
"""
Test script for updated Freshdesk to JIRA migration
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

def test_ticket_conversion(ticket_id: int = 55):
    """Test the updated ticket conversion"""
    print(f"Testing ticket conversion for ticket #{ticket_id}")
    
    # Initialize components
    data_loader = DataLoader()
    users_data = data_loader.load_users()
    user_mapper = UserMapper(users_data)
    ticket_converter = TicketConverter(user_mapper)
    
    # Load ticket data
    ticket = data_loader.load_ticket_details(ticket_id)
    if not ticket:
        print(f"Ticket {ticket_id} not found")
        return
    
    conversations = data_loader.load_conversations(ticket_id).get(ticket_id, [])
    ticket_attachments = data_loader.load_ticket_attachments(ticket_id).get(ticket_id, [])
    conv_attachments = data_loader.load_conversation_attachments(ticket_id).get(ticket_id, [])
    
    print(f"Loaded data:")
    print(f"  - Ticket: {ticket.get('subject', 'No subject')}")
    print(f"  - Conversations: {len(conversations)}")
    print(f"  - Ticket attachments: {len(ticket_attachments)}")
    print(f"  - Conversation attachments: {len(conv_attachments)}")
    
    # Convert to JIRA format
    jira_issue = ticket_converter.convert_to_jira_issue(
        ticket, 
        conversations, 
        ticket_attachments, 
        conv_attachments
    )
    
    print(f"\n=== JIRA Issue Summary ===")
    print(f"Summary: {jira_issue['fields']['summary']}")
    print(f"Priority: {jira_issue['fields']['priority']['name']}")
    print(f"Assignee: {jira_issue['fields']['assignee']['emailAddress']}")
    
    print(f"\n=== Custom Fields ===")
    print(f"FD_Reporter: {jira_issue['fields'].get('customfield_10292', 'N/A')}")
    print(f"FD_Assignee: {jira_issue['fields'].get('customfield_10293', 'N/A')}")
    print(f"FD_Priority: {jira_issue['fields'].get('customfield_10289', 'N/A')}")
    print(f"FD_Status: {jira_issue['fields'].get('customfield_10294', 'N/A')}")
    
    print(f"\n=== Description Preview ===")
    description = jira_issue['fields']['description']
    lines = description.split('\n')
    
    # Show first 20 lines
    for i, line in enumerate(lines[:20]):
        print(f"{i+1:2d}: {line}")
    
    if len(lines) > 20:
        print(f"... and {len(lines) - 20} more lines")
    
    # Save full description to file for inspection
    with open(f'ticket_{ticket_id}_description.txt', 'w', encoding='utf-8') as f:
        f.write(description)
    
    print(f"\nFull description saved to: ticket_{ticket_id}_description.txt")
    
    return jira_issue

def test_user_mapping():
    """Test user mapping functionality"""
    print("\n=== Testing User Mapping ===")
    
    data_loader = DataLoader()
    users_data = data_loader.load_users()
    user_mapper = UserMapper(users_data)
    
    # Test some user lookups
    test_users = [1, 2, 3, 100, 200]  # Some sample user IDs
    
    for user_id in test_users:
        user_info = user_mapper.get_user_by_id(user_id)
        if user_info:
            print(f"User {user_id}: {user_info['name']} ({user_info['email']}) - {user_info['type']}")
        else:
            print(f"User {user_id}: Not found")

if __name__ == "__main__":
    print("Testing Updated Freshdesk to JIRA Migration")
    print("=" * 50)
    
    # Test user mapping
    test_user_mapping()
    
    # Test ticket conversion
    ticket_id = 8991  # You can change this to test different tickets
    jira_issue = test_ticket_conversion(ticket_id)
    
    print(f"\nTest completed successfully!")
