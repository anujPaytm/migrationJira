#!/usr/bin/env python3
"""
Freshdesk to JIRA Migration Script
"""

import sys
import os
import time
import json
from typing import Dict, List, Any
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.jira_config import JiraConfig
from utils.data_loader import DataLoader
from utils.user_mapper import UserMapper
from utils.ticket_converter import TicketConverter
from utils.attachment_handler import AttachmentHandler

try:
    from jira import JIRA
except ImportError:
    print("Error: python-jira package not installed. Run: pip install python-jira")
    sys.exit(1)

class TicketMigrator:
    """Main migration class"""
    
    def __init__(self):
        self.config = JiraConfig()
        self.config.validate()
        
        # Initialize JIRA client
        self.jira = JIRA(
            options=self.config.get_jira_options(),
            basic_auth=self.config.get_auth()
        )
        
        # Initialize components
        self.data_loader = DataLoader()
        self.users_data = self.data_loader.load_users()
        self.user_mapper = UserMapper(self.users_data)
        self.ticket_converter = TicketConverter(self.user_mapper)
        self.attachment_handler = AttachmentHandler(self.jira)
        
        # Migration tracking
        self.migrated_tickets = []
        self.failed_tickets = []
        
    def migrate_single_ticket(self, ticket_id: int) -> bool:
        """Migrate a single ticket"""
        try:
            print(f"\n--- Migrating Ticket #{ticket_id} ---")
            
            # Load ticket data
            ticket = self.data_loader.load_ticket_details(ticket_id)
            if not ticket:
                print(f"Ticket {ticket_id} not found")
                return False
            
            conversations = self.data_loader.load_conversations(ticket_id).get(ticket_id, [])
            ticket_attachments = self.data_loader.load_ticket_attachments(ticket_id).get(ticket_id, [])
            conv_attachments = self.data_loader.load_conversation_attachments(ticket_id).get(ticket_id, [])
            
            # Convert to JIRA format
            jira_issue = self.ticket_converter.convert_to_jira_issue(ticket, conversations)
            
            if self.config.dry_run:
                print("DRY RUN - Would create issue:")
                print(json.dumps(jira_issue, indent=2))
                return True
            
            # Create JIRA issue
            print("Creating JIRA issue...")
            issue = self.jira.create_issue(fields=jira_issue['fields'])
            issue_key = issue.key
            print(f"Created issue: {issue_key}")
            
            # Upload attachments
            if ticket_attachments:
                print(f"Uploading {len(ticket_attachments)} ticket attachments...")
                uploaded = self.attachment_handler.process_ticket_attachments(
                    issue_key, ticket_id, ticket_attachments
                )
                print(f"Uploaded {uploaded} ticket attachments")
            
            if conv_attachments:
                print(f"Uploading {len(conv_attachments)} conversation attachments...")
                uploaded = self.attachment_handler.process_conversation_attachments(
                    issue_key, ticket_id, conv_attachments
                )
                print(f"Uploaded {uploaded} conversation attachments")
            
            # Track successful migration
            self.migrated_tickets.append({
                'ticket_id': ticket_id,
                'jira_key': issue_key,
                'subject': ticket.get('subject', ''),
                'status': 'success'
            })
            
            print(f"Successfully migrated ticket {ticket_id} to {issue_key}")
            return True
            
        except Exception as e:
            print(f"Failed to migrate ticket {ticket_id}: {e}")
            self.failed_tickets.append({
                'ticket_id': ticket_id,
                'error': str(e),
                'status': 'failed'
            })
            return False
    
    def migrate_tickets_batch(self, ticket_ids: List[int]) -> Dict[str, int]:
        """Migrate a batch of tickets"""
        success_count = 0
        failure_count = 0
        
        for ticket_id in ticket_ids:
            try:
                if self.migrate_single_ticket(ticket_id):
                    success_count += 1
                else:
                    failure_count += 1
                
                # Rate limiting
                time.sleep(self.config.retry_delay)
                
            except Exception as e:
                print(f"Unexpected error migrating ticket {ticket_id}: {e}")
                failure_count += 1
        
        return {'success': success_count, 'failure': failure_count}
    
    def migrate_all_tickets(self, limit: int = None) -> Dict[str, Any]:
        """Migrate all tickets"""
        print("Loading all ticket details...")
        all_tickets = self.data_loader.load_ticket_details()
        
        if not all_tickets:
            print("No tickets found to migrate")
            return {'success': 0, 'failure': 0, 'total': 0}
        
        ticket_ids = list(all_tickets.keys())
        if limit:
            ticket_ids = ticket_ids[:limit]
        
        print(f"Found {len(ticket_ids)} tickets to migrate")
        
        # Process in batches
        total_success = 0
        total_failure = 0
        
        for i in range(0, len(ticket_ids), self.config.batch_size):
            batch = ticket_ids[i:i + self.config.batch_size]
            print(f"\nProcessing batch {i//self.config.batch_size + 1}/{(len(ticket_ids) + self.config.batch_size - 1)//self.config.batch_size}")
            
            results = self.migrate_tickets_batch(batch)
            total_success += results['success']
            total_failure += results['failure']
            
            print(f"Batch completed: {results['success']} success, {results['failure']} failure")
        
        return {
            'success': total_success,
            'failure': total_failure,
            'total': len(ticket_ids),
            'migrated_tickets': self.migrated_tickets,
            'failed_tickets': self.failed_tickets
        }
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate migration report"""
        report = f"""
=== Freshdesk to JIRA Migration Report ===

Total Tickets: {results['total']}
Successful Migrations: {results['success']}
Failed Migrations: {results['failure']}
Success Rate: {(results['success']/results['total']*100):.1f}%

=== Successfully Migrated Tickets ===
"""
        
        for ticket in results['migrated_tickets']:
            report += f"Freshdesk #{ticket['ticket_id']} → JIRA {ticket['jira_key']}: {ticket['subject']}\n"
        
        if results['failed_tickets']:
            report += "\n=== Failed Migrations ===\n"
            for ticket in results['failed_tickets']:
                report += f"Freshdesk #{ticket['ticket_id']}: {ticket['error']}\n"
        
        return report
    
    def cleanup(self):
        """Cleanup resources"""
        self.attachment_handler.cleanup()

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate Freshdesk tickets to JIRA')
    parser.add_argument('--ticket-id', type=int, help='Migrate specific ticket ID')
    parser.add_argument('--limit', type=int, help='Limit number of tickets to migrate')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode')
    
    args = parser.parse_args()
    
    # Override dry-run setting if specified
    if args.dry_run:
        os.environ['DRY_RUN'] = 'true'
    
    migrator = TicketMigrator()
    
    try:
        if args.ticket_id:
            # Migrate single ticket
            success = migrator.migrate_single_ticket(args.ticket_id)
            if success:
                print(f"Successfully migrated ticket {args.ticket_id}")
            else:
                print(f"Failed to migrate ticket {args.ticket_id}")
        else:
            # Migrate all tickets
            results = migrator.migrate_all_tickets(limit=args.limit)
            report = migrator.generate_report(results)
            print(report)
            
            # Save report to file
            with open('migration_report.txt', 'w') as f:
                f.write(report)
            print("\nReport saved to migration_report.txt")
    
    finally:
        migrator.cleanup()

if __name__ == "__main__":
    main()
