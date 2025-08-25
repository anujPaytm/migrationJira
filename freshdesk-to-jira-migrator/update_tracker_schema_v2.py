#!/usr/bin/env python3
"""
Script to update the migration tracker CSV schema to add attachment_type column.
"""

import csv
import os
from pathlib import Path

def update_tracker_schema():
    """Update the migration tracker CSV to add attachment_type column."""
    tracker_file = Path("tracker/migration_tracker.csv")
    
    if not tracker_file.exists():
        print("❌ Tracker file not found")
        return
    
    # Create backup
    backup_file = tracker_file.with_suffix('.csv.backup')
    print(f"📋 Creating backup: {backup_file}")
    
    # Read existing data
    rows = []
    with open(tracker_file, 'r', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"📊 Found {len(rows)} existing records")
    
    # Write new CSV with attachment_type column
    with open(tracker_file, 'w', newline='') as f:
        fieldnames = [
            'ticket_id', 'jira_status', 'jira_id', 'reason', 
            'total_attachments', 'successful_attachments', 'failed_attachments',
            'attachment_type', 'created_at', 'updated_at'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in rows:
            # Add attachment_type field with default value
            row['attachment_type'] = 'none'
            writer.writerow(row)
    
    print("✅ Successfully updated tracker schema with attachment_type column")
    print("📋 New schema includes: ticket_id, jira_status, jira_id, reason, total_attachments, successful_attachments, failed_attachments, attachment_type, created_at, updated_at")

if __name__ == "__main__":
    update_tracker_schema()
