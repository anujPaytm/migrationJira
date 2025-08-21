#!/usr/bin/env python3
"""
Test actual migration to JIRA with updated code
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.migrate_tickets import TicketMigrator

def test_actual_migration(ticket_id: int = 8991):
    """Test actual migration to JIRA"""
    print(f"Testing actual migration for ticket #{ticket_id}")
    
    # Initialize migrator
    migrator = TicketMigrator()
    
    # Test single ticket migration
    success = migrator.migrate_single_ticket(ticket_id)
    
    if success:
        print(f"✅ Successfully migrated ticket {ticket_id} to JIRA!")
        
        # Show migration results
        if migrator.migrated_tickets:
            for result in migrator.migrated_tickets:
                print(f"  - Ticket {result['ticket_id']} → {result['jira_key']}")
                print(f"    Subject: {result['subject']}")
    else:
        print(f"❌ Failed to migrate ticket {ticket_id}")
        
        # Show error details
        if migrator.failed_tickets:
            for result in migrator.failed_tickets:
                print(f"  - Error: {result['error']}")
    
    return success

if __name__ == "__main__":
    print("Testing Actual Migration to JIRA")
    print("=" * 40)
    
    # Test with ticket 55 (simpler ticket)
    ticket_id = 55
    success = test_actual_migration(ticket_id)
    
    if success:
        print(f"\n🎉 Migration test completed successfully!")
        print(f"Check your JIRA project to see the migrated ticket.")
    else:
        print(f"\n💥 Migration test failed. Check the error messages above.")
