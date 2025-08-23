"""
Migration tracker utility for managing CSV-based migration status.
"""

import csv
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


class MigrationTracker:
    """
    Manages migration status tracking using CSV files.
    """
    
    def __init__(self, tracker_file: str = "tracker/migration_tracker.csv"):
        """
        Initialize the migration tracker.
        
        Args:
            tracker_file: Path to the CSV tracker file
        """
        self.tracker_file = Path(tracker_file)
        self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize_tracker()
    
    def _initialize_tracker(self):
        """Initialize the tracker CSV file with headers if it doesn't exist."""
        with self._lock:
            if not self.tracker_file.exists():
                with open(self.tracker_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'ticket_id', 'jira_status', 'jira_id', 'reason', 
                        'created_at', 'updated_at'
                    ])
    
    def get_ticket_status(self, ticket_id: int) -> Optional[Dict[str, str]]:
        """
        Get the current status of a ticket.
        
        Args:
            ticket_id: Freshdesk ticket ID
            
        Returns:
            Status dictionary or None if not found
        """
        try:
            with open(self.tracker_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row['ticket_id']) == ticket_id:
                        return row
        except FileNotFoundError:
            pass
        return None
    
    def _get_ticket_status_internal(self, ticket_id: int) -> Optional[Dict[str, str]]:
        """
        Internal method to get ticket status without holding the main lock.
        """
        try:
            with open(self.tracker_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row['ticket_id']) == ticket_id:
                        return row
        except FileNotFoundError:
            pass
        return None
    
    def update_ticket_status(self, ticket_id: int, jira_status: str, 
                           jira_id: str = None, reason: str = None):
        """
        Update the status of a ticket.
        
        Args:
            ticket_id: Freshdesk ticket ID
            jira_status: Status (success, failed, in_progress, etc.)
            jira_id: JIRA issue key (if successful)
            reason: Reason for failure (if failed)
        """
        try:
            with self._lock:
                current_time = datetime.now().isoformat()
                
                # Check if ticket already exists (without holding the lock)
                existing_status = self._get_ticket_status_internal(ticket_id)
                
                if existing_status:
                    # Update existing record
                    self._update_existing_record(ticket_id, jira_status, jira_id, reason, current_time)
                else:
                    # Add new record
                    self._add_new_record(ticket_id, jira_status, jira_id, reason, current_time)
        except Exception as e:
            print(f"❌ Error updating tracker for ticket {ticket_id}: {str(e)}")
            # Don't re-raise the exception to prevent migration failure
    
    def _update_existing_record(self, ticket_id: int, jira_status: str, 
                              jira_id: str, reason: str, updated_at: str):
        """Update an existing record in the CSV."""
        rows = []
        try:
            with open(self.tracker_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except FileNotFoundError:
            rows = []
        except Exception as e:
            print(f"❌ Error reading tracker file: {str(e)}")
            rows = []
        
        # Update the specific row
        updated = False
        for row in rows:
            try:
                if int(row['ticket_id']) == ticket_id:
                    row['jira_status'] = jira_status
                    if jira_id:
                        row['jira_id'] = jira_id
                    if reason:
                        row['reason'] = reason
                    row['updated_at'] = updated_at
                    updated = True
                    break
            except (ValueError, KeyError) as e:
                print(f"❌ Error processing row for ticket {ticket_id}: {str(e)}")
                continue
        
        if not updated:
            print(f"⚠️ Ticket {ticket_id} not found in tracker, adding new record")
            self._add_new_record(ticket_id, jira_status, jira_id, reason, updated_at)
            return
        
        # Write back to file
        try:
            with open(self.tracker_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'ticket_id', 'jira_status', 'jira_id', 'reason', 
                    'created_at', 'updated_at'
                ])
                writer.writeheader()
                writer.writerows(rows)
        except Exception as e:
            print(f"❌ Error writing tracker file: {str(e)}")
            raise
    
    def _add_new_record(self, ticket_id: int, jira_status: str, 
                       jira_id: str, reason: str, created_at: str):
        """Add a new record to the CSV."""
        with open(self.tracker_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                ticket_id, jira_status, jira_id or '', reason or '', 
                created_at, created_at
            ])
    
    def get_migration_summary(self) -> Dict[str, int]:
        """
        Get a summary of migration status.
        
        Returns:
            Dictionary with status counts
        """
        with self._lock:
            summary = {
                'total': 0,
                'success': 0,
                'failed': 0,
                'in_progress': 0,
                'pending': 0
            }
            
            with open(self.tracker_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    summary['total'] += 1
                    status = row['jira_status'].lower()
                    if status in summary:
                        summary[status] += 1
                    else:
                        summary['pending'] += 1
            
            return summary
    
    def get_failed_tickets(self) -> List[Dict[str, str]]:
        """
        Get list of failed tickets with reasons.
        
        Returns:
            List of failed ticket dictionaries
        """
        failed_tickets = []
        
        with open(self.tracker_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['jira_status'].lower() == 'failed':
                    failed_tickets.append(row)
        
        return failed_tickets
    
    def get_successful_tickets(self) -> List[Dict[str, str]]:
        """
        Get list of successfully migrated tickets.
        
        Returns:
            List of successful ticket dictionaries
        """
        successful_tickets = []
        
        with open(self.tracker_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['jira_status'].lower() == 'success':
                    successful_tickets.append(row)
        
        return successful_tickets
