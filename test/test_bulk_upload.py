#!/usr/bin/env python3
"""
Test script for bulk attachment upload methods
"""

import sys
import os
sys.path.append('.')

from utils.bulk_attachment_handler import BulkAttachmentHandler
from utils.data_loader import DataLoader
from utils.user_mapper import UserMapper
from utils.ticket_converter import TicketConverter
from utils.attachment_handler import AttachmentHandler
from config.jira_config import JiraConfig
from jira import JIRA

def test_bulk_upload():
    """Test bulk upload methods"""
    print("Testing Bulk Upload Methods")
    print("=" * 50)
    
    # Initialize handlers
    bulk_handler = BulkAttachmentHandler()
    config = JiraConfig()
    jira = JIRA(options=config.get_jira_options(), basic_auth=config.get_auth())
    
    # Load test data
    data_loader = DataLoader()
    users_data = data_loader.load_users()
    user_mapper = UserMapper(users_data)
    
    # Get ticket 55 data
    ticket = data_loader.load_ticket_details(55)
    ticket_attachments = data_loader.load_ticket_attachments(55).get(55, [])
    
    print(f"Found {len(ticket_attachments)} ticket attachments")
    
    # Create a test issue
    converter = TicketConverter(user_mapper)
    jira_issue = converter.convert_to_jira_issue(ticket, [], ticket_attachments, [])
    
    print("Creating test issue...")
    issue = jira.create_issue(fields=jira_issue["fields"])
    print(f"✅ Created test issue: {issue.key}")
    
    # Prepare file paths for attachments
    file_paths = []
    for attachment in ticket_attachments:
        filename = attachment.get('name', '')
        file_path = f"../data_to_be_migrated/attachments/{ticket.get('id')}/{filename}"
        if os.path.exists(file_path):
            file_paths.append(file_path)
        else:
            print(f"⚠️  File not found: {file_path}")
    
    print(f"Found {len(file_paths)} valid files to upload")
    
    if not file_paths:
        print("❌ No files to upload, skipping tests")
        return
    
    # Test 1: Bulk upload (single request)
    print("\n" + "="*50)
    print("TEST 1: Bulk Upload (Single Request)")
    print("="*50)
    
    try:
        results = bulk_handler.upload_attachments_bulk(issue.key, file_paths)
        success_count = sum(results)
        print(f"Bulk upload results: {success_count}/{len(file_paths)} successful")
    except Exception as e:
        print(f"❌ Bulk upload test failed: {e}")
    
    # Test 2: Parallel upload (multiple concurrent requests)
    print("\n" + "="*50)
    print("TEST 2: Parallel Upload (Concurrent Requests)")
    print("="*50)
    
    try:
        results = bulk_handler.upload_attachments_parallel(issue.key, file_paths)
        success_count = sum(results)
        print(f"Parallel upload results: {success_count}/{len(file_paths)} successful")
    except Exception as e:
        print(f"❌ Parallel upload test failed: {e}")
    
    # Test 3: Original method (sequential)
    print("\n" + "="*50)
    print("TEST 3: Original Method (Sequential)")
    print("="*50)
    
    try:
        original_handler = AttachmentHandler(jira)
        success_count = 0
        for file_path in file_paths:
            if original_handler.upload_attachment_to_jira(issue.key, file_path):
                success_count += 1
        print(f"Sequential upload results: {success_count}/{len(file_paths)} successful")
    except Exception as e:
        print(f"❌ Sequential upload test failed: {e}")
    
    print("\n" + "="*50)
    print("TESTING COMPLETED")
    print("="*50)
    
    # Clean up - delete test issue
    try:
        issue.delete()
        print(f"✅ Cleaned up test issue: {issue.key}")
    except:
        print(f"⚠️  Could not delete test issue: {issue.key}")

if __name__ == "__main__":
    test_bulk_upload()
