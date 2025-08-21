#!/usr/bin/env python3
"""
Main migration script for converting Freshdesk tickets to JIRA issues.
Orchestrates the entire migration process with configurable field mapping.
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any, Optional
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add project root and src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from jira import JIRA
from core.data_loader import DataLoader
from core.field_mapper import FieldMapper
from core.ticket_converter import TicketConverter
from utils.bulk_upload import BulkAttachmentUploader


class JiraConfig:
    """JIRA configuration class."""
    
    def __init__(self):
        """Initialize JIRA configuration from environment variables."""
        self.domain = os.getenv('JIRA_DOMAIN')
        self.email = os.getenv('JIRA_EMAIL')
        self.api_token = os.getenv('JIRA_API_TOKEN')
        self.project_key = os.getenv('JIRA_PROJECT_KEY', 'FTJM')
        
        if not all([self.domain, self.email, self.api_token]):
            raise ValueError("Missing required JIRA environment variables")


class TicketMigrator:
    """
    Main migration orchestrator for converting Freshdesk tickets to JIRA.
    """
    
    def __init__(self, config: JiraConfig, data_directory: str = "../data_to_be_migrated"):
        """
        Initialize the ticket migrator.
        
        Args:
            config: JIRA configuration
            data_directory: Path to Freshdesk data directory
        """
        self.config = config
        self.jira = JIRA(
            server=f"https://{config.domain}",
            basic_auth=(config.email, config.api_token)
        )
        
        # Initialize components
        self.data_loader = DataLoader(data_directory)
        self.field_mapper = FieldMapper()
        self.ticket_converter = TicketConverter(self.field_mapper)
        self.bulk_uploader = BulkAttachmentUploader({
            'domain': config.domain,
            'email': config.email,
            'api_token': config.api_token
        })
        
        # Migration statistics
        self.stats = {
            'total_tickets': 0,
            'successful_migrations': 0,
            'failed_migrations': 0,
            'total_attachments': 0,
            'successful_attachments': 0
        }
    
    def validate_setup(self) -> bool:
        """
        Validate the migration setup.
        
        Returns:
            True if setup is valid, False otherwise
        """
        print("🔍 Validating migration setup...")
        
        # Validate data directory
        if not self.data_loader.validate_data_directory():
            print("❌ Data directory validation failed")
            return False
        
        # Validate JIRA connection
        try:
            myself = self.jira.myself()
            print(f"✅ Connected to JIRA as: {myself.get('displayName', 'Unknown')}")
        except Exception as e:
            print(f"❌ JIRA connection failed: {e}")
            return False
        
        # Validate project access
        try:
            project = self.jira.project(self.config.project_key)
            print(f"✅ Project access confirmed: {project.name} ({project.key})")
        except Exception as e:
            print(f"❌ Project access failed: {e}")
            return False
        
        # Get data summary
        data_summary = self.data_loader.get_data_summary()
        print(f"📊 Data summary: {data_summary['total_tickets']} tickets available")
        
        return True
    
    def migrate_single_ticket(self, ticket_id: int, dry_run: bool = False) -> bool:
        """
        Migrate a single ticket to JIRA.
        
        Args:
            ticket_id: Freshdesk ticket ID
            dry_run: If True, don't actually create the JIRA issue
            
        Returns:
            True if successful, False otherwise
        """
        print(f"\n🔄 Migrating ticket {ticket_id}...")
        
        try:
            # Load ticket data
            ticket_data = self.data_loader.load_ticket_data(ticket_id)
            
            if not ticket_data['ticket_details']:
                print(f"❌ No ticket details found for ticket {ticket_id}")
                return False
            
            # Convert to JIRA issue
            jira_issue = self.ticket_converter.convert_to_jira_issue(
                ticket=ticket_data['ticket_details'],
                conversations=ticket_data['conversations'],
                ticket_attachments=ticket_data['ticket_attachments'],
                conversation_attachments=ticket_data['conversation_attachments'],
                user_data=ticket_data['user_data']
            )
            
            # Set project key
            self.ticket_converter.set_project_key(jira_issue, self.config.project_key)
            
            if dry_run:
                print(f"🔍 Dry run - would create issue:")
                print(json.dumps(jira_issue, indent=2))
                return True
            
            # Create JIRA issue
            issue = self.jira.create_issue(fields=jira_issue['fields'])
            print(f"✅ Created JIRA issue: {issue.key}")
            
            # Upload attachments
            self._upload_attachments(issue.key, ticket_data)
            
            self.stats['successful_migrations'] += 1
            return True
            
        except Exception as e:
            print(f"❌ Failed to migrate ticket {ticket_id}: {e}")
            self.stats['failed_migrations'] += 1
            return False
    
    def _upload_attachments(self, issue_key: str, ticket_data: Dict[str, Any]):
        """
        Upload attachments for a ticket.
        
        Args:
            issue_key: JIRA issue key
            ticket_data: Ticket data dictionary
        """
        ticket_id = ticket_data['ticket_id']
        ticket_attachments = ticket_data['ticket_attachments']
        conversation_attachments = ticket_data['conversation_attachments']
        
        # Upload ticket attachments
        if ticket_attachments:
            print(f"📎 Uploading {len(ticket_attachments)} ticket attachments...")
            attachment_data = []
            
            for attachment in ticket_attachments:
                filename = attachment.get('name', '')
                file_path = self.data_loader.get_attachment_file_path(ticket_id, filename)
                if file_path:
                    attachment_data.append({
                        'file_path': file_path,
                        'attachment_id': attachment.get('id', ''),
                        'original_name': filename
                    })
            
            if attachment_data:
                results = self.bulk_uploader.upload_attachments_with_renaming(issue_key, attachment_data)
                successful = sum(results)
                self.stats['total_attachments'] += len(attachment_data)
                self.stats['successful_attachments'] += successful
                print(f"✅ Uploaded {successful}/{len(attachment_data)} ticket attachments")
            else:
                print("⚠️  No valid ticket attachment files found")
        
        # Upload conversation attachments
        if conversation_attachments:
            print(f"📎 Uploading {len(conversation_attachments)} conversation attachments...")
            attachment_data = []
            
            for attachment in conversation_attachments:
                filename = attachment.get('name', '')
                file_path = self.data_loader.get_attachment_file_path(ticket_id, filename)
                if file_path:
                    attachment_data.append({
                        'file_path': file_path,
                        'attachment_id': attachment.get('id', ''),
                        'original_name': filename
                    })
            
            if attachment_data:
                results = self.bulk_uploader.upload_attachments_with_renaming(issue_key, attachment_data)
                successful = sum(results)
                self.stats['total_attachments'] += len(attachment_data)
                self.stats['successful_attachments'] += successful
                print(f"✅ Uploaded {successful}/{len(attachment_data)} conversation attachments")
            else:
                print("⚠️  No valid conversation attachment files found")
    
    def migrate_tickets(self, ticket_ids: List[int], dry_run: bool = False) -> Dict[str, Any]:
        """
        Migrate multiple tickets to JIRA.
        
        Args:
            ticket_ids: List of ticket IDs to migrate
            dry_run: If True, don't actually create JIRA issues
            
        Returns:
            Migration statistics
        """
        print(f"🚀 Starting migration of {len(ticket_ids)} tickets...")
        print(f"Mode: {'Dry Run' if dry_run else 'Live Migration'}")
        
        self.stats['total_tickets'] = len(ticket_ids)
        
        for i, ticket_id in enumerate(ticket_ids, 1):
            print(f"\n📋 Progress: {i}/{len(ticket_ids)}")
            self.migrate_single_ticket(ticket_id, dry_run)
        
        return self._get_migration_summary()
    
    def _get_migration_summary(self) -> Dict[str, Any]:
        """
        Get migration summary statistics.
        
        Returns:
            Migration summary dictionary
        """
        return {
            'total_tickets': self.stats['total_tickets'],
            'successful_migrations': self.stats['successful_migrations'],
            'failed_migrations': self.stats['failed_migrations'],
            'success_rate': self.stats['successful_migrations'] / self.stats['total_tickets'] if self.stats['total_tickets'] > 0 else 0,
            'total_attachments': self.stats['total_attachments'],
            'successful_attachments': self.stats['successful_attachments'],
            'attachment_success_rate': self.stats['successful_attachments'] / self.stats['total_attachments'] if self.stats['total_attachments'] > 0 else 0
        }


def main():
    """Main function for the migration script."""
    parser = argparse.ArgumentParser(description='Migrate Freshdesk tickets to JIRA')
    parser.add_argument('--ticket-ids', nargs='+', type=int, help='Specific ticket IDs to migrate')
    parser.add_argument('--all', action='store_true', help='Migrate all available tickets')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without creating JIRA issues')
    parser.add_argument('--data-dir', default='../data_to_be_migrated', help='Path to Freshdesk data directory')
    parser.add_argument('--limit', type=int, help='Limit number of tickets to migrate')
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = JiraConfig()
        
        # Initialize migrator
        migrator = TicketMigrator(config, args.data_dir)
        
        # Validate setup
        if not migrator.validate_setup():
            print("❌ Setup validation failed. Exiting.")
            sys.exit(1)
        
        # Determine which tickets to migrate
        if args.ticket_ids:
            ticket_ids = args.ticket_ids
        elif args.all:
            ticket_ids = migrator.data_loader.load_all_ticket_ids()
        else:
            print("❌ Please specify --ticket-ids or --all")
            sys.exit(1)
        
        # Apply limit if specified
        if args.limit:
            ticket_ids = ticket_ids[:args.limit]
        
        if not ticket_ids:
            print("❌ No tickets to migrate")
            sys.exit(1)
        
        # Perform migration
        summary = migrator.migrate_tickets(ticket_ids, args.dry_run)
        
        # Print summary
        print(f"\n📊 Migration Summary:")
        print(f"Total tickets: {summary['total_tickets']}")
        print(f"Successful: {summary['successful_migrations']}")
        print(f"Failed: {summary['failed_migrations']}")
        print(f"Success rate: {summary['success_rate']:.2%}")
        print(f"Total attachments: {summary['total_attachments']}")
        print(f"Successful attachments: {summary['successful_attachments']}")
        print(f"Attachment success rate: {summary['attachment_success_rate']:.2%}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
