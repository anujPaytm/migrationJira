#!/usr/bin/env python3
"""
Main migration script for converting Freshdesk tickets to JIRA issues.
Orchestrates the entire migration process with configurable field mapping.
"""

import os
import sys
import json
import argparse
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add project root and src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Ensure the src directory is treated as a Python package
src_path = project_root / "src"
if not (src_path / "__init__.py").exists():
    (src_path / "__init__.py").touch()

from jira import JIRA
from core.data_loader import DataLoader
from core.field_mapper import FieldMapper
from core.ticket_converter import TicketConverter
from utils.bulk_upload import BulkAttachmentUploader
from utils.tracker import MigrationTracker
from utils.logger import get_logger


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
    
    def __init__(self, config: JiraConfig, data_directory: str = "../data_to_be_migrated", max_workers: int = 8, log_file: str = None):
                """
                Initialize the ticket migrator.
                
                Args:
                    config: JIRA configuration
                    data_directory: Path to Freshdesk data directory
                    max_workers: Maximum number of parallel workers
                    log_file: Path to log file (optional)
                """
                self.config = config
                self.max_workers = max_workers
                
                # Initialize logger
                self.logger = get_logger(log_file, "INFO")
                
                # Rate limiting
                self.rate_limit_lock = threading.Lock()
                self.last_request_time = 0
                self.min_request_interval = 0.1  # 100ms between requests (10 requests per second)
                
                # Initialize components
                self.data_loader = DataLoader(data_directory)
                self.field_mapper = FieldMapper()
                self.ticket_converter = TicketConverter(self.field_mapper)
                self.bulk_uploader = BulkAttachmentUploader({
                    'domain': config.domain,
                    'email': config.email,
                    'api_token': config.api_token
                })
                self.tracker = MigrationTracker()
                
                # Migration statistics with thread safety
                self.stats_lock = threading.Lock()
                self.stats = {
                    'total_tickets': 0,
                    'successful_migrations': 0,
                    'failed_migrations': 0,
                    'total_attachments': 0,
                    'successful_attachments': 0
                }
    
    def _rate_limit(self):
        """Implement rate limiting for API requests."""
        with self.rate_limit_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                time.sleep(self.min_request_interval - time_since_last)
            self.last_request_time = time.time()
    
    def _get_jira_client(self) -> JIRA:
        """Get a JIRA client with rate limiting."""
        self._rate_limit()
        return JIRA(
            server=f"https://{self.config.domain}",
            basic_auth=(self.config.email, self.config.api_token)
        )
    
    def validate_setup(self) -> bool:
        """
        Validate the migration setup.
        
        Returns:
            True if setup is valid, False otherwise
        """
        self.logger.info("Validating migration setup...")
        
        # Validate data directory
        if not self.data_loader.validate_data_directory():
            self.logger.error("Data directory validation failed")
            return False
        
        # Validate JIRA connection
        try:
            jira = self._get_jira_client()
            myself = jira.myself()
            self.logger.setup_validation("JIRA Connection", True, f"Connected as: {myself.get('displayName', 'Unknown')}")
        except Exception as e:
            self.logger.setup_validation("JIRA Connection", False, str(e))
            return False
        
        # Validate project access
        try:
            jira = self._get_jira_client()
            project = jira.project(self.config.project_key)
            self.logger.setup_validation("Project Access", True, f"{project.name} ({project.key})")
        except Exception as e:
            self.logger.setup_validation("Project Access", False, str(e))
            return False
        
        # Get data summary
        data_summary = self.data_loader.get_data_summary()
        self.logger.info(f"Data summary: {data_summary['total_tickets']} tickets available")
        
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
        print(f"🔄 Starting migration for ticket {ticket_id}")
        
        # Check if ticket is already processed
        existing_status = self.tracker.get_ticket_status(ticket_id)
        if existing_status and existing_status.get('jira_status') in ['success', 'dry_run_completed']:
            print(f"⏭️  Skipping ticket {ticket_id} - already processed (status: {existing_status.get('jira_status')})")
            return True
        
        try:
            # Load ticket data
            print(f"📂 Loading ticket data for {ticket_id}...")
            ticket_data = self.data_loader.load_ticket_data(ticket_id)
            
            if not ticket_data['ticket_details']:
                error_msg = f"No ticket details found for ticket {ticket_id}"
                print(f"❌ {error_msg}")
                self.tracker.update_ticket_status(ticket_id, "failed", reason=error_msg)
                return False
            
            # Convert to JIRA issue
            print(f"🔄 Converting ticket {ticket_id} to JIRA format...")
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
                print(f"✅ Dry run - would create issue for ticket {ticket_id}")
                self.tracker.update_ticket_status(ticket_id, "dry_run_completed")
                
                with self.stats_lock:
                    self.stats['successful_migrations'] += 1
                
                return True
            
            # Create JIRA issue
            print(f"🚀 Creating JIRA issue for ticket {ticket_id}...")
            jira = self._get_jira_client()
            issue = jira.create_issue(fields=jira_issue['fields'])
            print(f"✅ Created JIRA issue: {issue.key}")
            
            # Upload attachments
            self._upload_attachments(issue.key, ticket_data)
            
            print(f"✅ Successfully migrated ticket {ticket_id} to {issue.key}")
            
            # Update tracker with success
            self.tracker.update_ticket_status(ticket_id, "success", jira_id=issue.key)
            
            with self.stats_lock:
                self.stats['successful_migrations'] += 1
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to migrate ticket {ticket_id}: {str(e)}"
            print(f"❌ {error_msg}")
            
            # Update tracker with failure
            self.tracker.update_ticket_status(ticket_id, "failed", reason=error_msg)
            
            with self.stats_lock:
                self.stats['failed_migrations'] += 1
            
            return False
    
    def _migrate_ticket_worker(self, args: Tuple[int, bool]) -> Tuple[int, bool]:
        """
        Worker function for parallel ticket migration.
        
        Args:
            args: Tuple of (ticket_id, dry_run)
            
        Returns:
            Tuple of (ticket_id, success)
        """
        ticket_id, dry_run = args
        try:
            success = self.migrate_single_ticket(ticket_id, dry_run)
            return (ticket_id, success)
        except Exception as e:
            error_msg = f"Worker failed for ticket {ticket_id}: {str(e)}"
            print(f"❌ {error_msg}")
            
            # Update tracker with failure
            self.tracker.update_ticket_status(ticket_id, "failed", reason=error_msg)
            
            with self.stats_lock:
                self.stats['failed_migrations'] += 1
            
            return (ticket_id, False)
    
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
                print(f"📎 Uploaded {successful}/{len(attachment_data)} ticket attachments")
                
                with self.stats_lock:
                    self.stats['total_attachments'] += len(attachment_data)
                    self.stats['successful_attachments'] += successful
            else:
                print("⚠️ No valid ticket attachment files found")
        
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
                print(f"📎 Uploaded {successful}/{len(attachment_data)} conversation attachments")
                
                with self.stats_lock:
                    self.stats['total_attachments'] += len(attachment_data)
                    self.stats['successful_attachments'] += successful
            else:
                print("⚠️ No valid conversation attachment files found")
    
    def migrate_tickets(self, ticket_ids: List[int], dry_run: bool = False, parallel: bool = True) -> Dict[str, Any]:
        """
        Migrate multiple tickets to JIRA.
        
        Args:
            ticket_ids: List of ticket IDs to migrate
            dry_run: If True, don't actually create JIRA issues
            parallel: If True, use parallel processing
            
        Returns:
            Migration statistics
        """
        self.logger.info(f"Starting migration of {len(ticket_ids)} tickets...")
        self.logger.info(f"Mode: {'Dry Run' if dry_run else 'Live Migration'}")
        self.logger.info(f"Processing: {'Parallel' if parallel else 'Sequential'}")
        
        with self.stats_lock:
            self.stats['total_tickets'] = len(ticket_ids)
            self.stats['successful_migrations'] = 0
            self.stats['failed_migrations'] = 0
        
        if parallel and len(ticket_ids) > 1:
            return self._migrate_tickets_parallel(ticket_ids, dry_run)
        else:
            return self._migrate_tickets_sequential(ticket_ids, dry_run)
    
    def _migrate_tickets_parallel(self, ticket_ids: List[int], dry_run: bool = False) -> Dict[str, Any]:
        """
        Migrate tickets using parallel processing.
        
        Args:
            ticket_ids: List of ticket IDs to migrate
            dry_run: If True, don't actually create JIRA issues
            
        Returns:
            Migration statistics
        """
        self.logger.info(f"Using {self.max_workers} parallel workers...")
        
        # Prepare arguments for workers
        worker_args = [(ticket_id, dry_run) for ticket_id in ticket_ids]
        
        # Track progress
        completed = 0
        total = len(ticket_ids)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_ticket = {
                executor.submit(self._migrate_ticket_worker, args): args[0] 
                for args in worker_args
            }
            
            # Process completed tasks
            for future in as_completed(future_to_ticket):
                ticket_id, success = future.result()
                completed += 1
                self.logger.progress(completed, total, ticket_id, "SUCCESS" if success else "FAILED")
        
        return self._get_migration_summary()
    
    def _migrate_tickets_sequential(self, ticket_ids: List[int], dry_run: bool = False) -> Dict[str, Any]:
        """
        Migrate tickets sequentially.
        
        Args:
            ticket_ids: List of ticket IDs to migrate
            dry_run: If True, don't actually create JIRA issues
            
        Returns:
            Migration statistics
        """
        for i, ticket_id in enumerate(ticket_ids, 1):
            self.logger.progress(i, len(ticket_ids))
            self.migrate_single_ticket(ticket_id, dry_run)
        
        return self._get_migration_summary()
    
    def _get_migration_summary(self) -> Dict[str, Any]:
        """
        Get migration summary statistics.
        
        Returns:
            Migration summary dictionary
        """
        # Get tracker summary
        tracker_summary = self.tracker.get_migration_summary()
        
        summary = {
            'total_tickets': self.stats['total_tickets'],
            'successful_migrations': self.stats['successful_migrations'],
            'failed_migrations': self.stats['failed_migrations'],
            'success_rate': self.stats['successful_migrations'] / self.stats['total_tickets'] if self.stats['total_tickets'] > 0 else 0,
            'total_attachments': self.stats['total_attachments'],
            'successful_attachments': self.stats['successful_attachments'],
            'attachment_success_rate': self.stats['successful_attachments'] / self.stats['total_attachments'] if self.stats['total_attachments'] > 0 else 0,
            'tracker_summary': tracker_summary
        }
        
        # Log summary
        self.logger.summary(summary)
        
        return summary


def main():
    """Main function for the migration script."""
    # Check if command-line arguments are provided (for backward compatibility)
    if len(sys.argv) > 1:
        # Use command-line arguments if provided
        parser = argparse.ArgumentParser(description='Migrate Freshdesk tickets to JIRA')
        parser.add_argument('--ticket-ids', nargs='+', type=int, help='Specific ticket IDs to migrate')
        parser.add_argument('--all', action='store_true', help='Migrate all available tickets')
        parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without creating JIRA issues')
        parser.add_argument('--data-dir', default='../data_to_be_migrated', help='Path to Freshdesk data directory')
        parser.add_argument('--limit', type=int, help='Limit number of tickets to migrate')
        parser.add_argument('--workers', type=int, default=8, help='Number of parallel workers (default: 8)')
        parser.add_argument('--sequential', action='store_true', help='Use sequential processing instead of parallel')
        parser.add_argument('--log-file', help='Path to log file (optional)')
        
        args = parser.parse_args()
        
        # Use command-line arguments
        data_dir = args.data_dir
        max_workers = args.workers
        log_file = args.log_file
        dry_run = args.dry_run
        sequential = args.sequential
        
        # Determine which tickets to migrate
        if args.ticket_ids:
            ticket_ids = args.ticket_ids
        elif args.all:
            ticket_ids = None  # Will be loaded from data loader
        else:
            print("❌ Please specify --ticket-ids or --all")
            sys.exit(1)
        
        limit = args.limit
        
    else:
        # Use environment variables
        data_dir = os.getenv('DATA_DIRECTORY', '../data_to_be_migrated')
        max_workers = int(os.getenv('PARALLEL_WORKERS', '8'))
        log_file = os.getenv('LOG_FILE', '')
        dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
        sequential = os.getenv('SEQUENTIAL_MODE', 'false').lower() == 'true'
        migrate_all = os.getenv('MIGRATE_ALL', 'false').lower() == 'true'
        limit = int(os.getenv('MIGRATION_LIMIT', '0'))
        
        # Parse ticket IDs from environment
        ticket_ids_str = os.getenv('TICKET_IDS', '')
        if ticket_ids_str:
            ticket_ids = [int(tid.strip()) for tid in ticket_ids_str.split(',') if tid.strip()]
        elif migrate_all:
            ticket_ids = None  # Will be loaded from data loader
        else:
            print("❌ Please set TICKET_IDS in .env or set MIGRATE_ALL=true")
            sys.exit(1)
    
    try:
        # Load configuration
        config = JiraConfig()
        
        # Initialize migrator with logger
        migrator = TicketMigrator(config, data_dir, max_workers=max_workers, log_file=log_file if log_file else None)
        
        # Validate setup
        if not migrator.validate_setup():
            migrator.logger.error("Setup validation failed. Exiting.")
            sys.exit(1)
        
        # Load ticket IDs if not provided
        if ticket_ids is None:
            ticket_ids = migrator.data_loader.load_all_ticket_ids()
        
        # Apply limit if specified
        if limit and limit > 0:
            ticket_ids = ticket_ids[:limit]
        
        if not ticket_ids:
            migrator.logger.error("No tickets to migrate")
            sys.exit(1)
        
        # Perform migration
        summary = migrator.migrate_tickets(ticket_ids, dry_run, parallel=not sequential)
        
        # Summary is already logged by the logger
        
    except Exception as e:
        # Try to get logger if available, otherwise use print
        try:
            migrator.logger.error(f"Migration failed: {e}")
        except:
            print(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
