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
from datetime import datetime
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
        self.issue_type = os.getenv('JIRA_ISSUE_TYPE', 'FD_Migration')
        
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
        
        # Initialize logger with DEBUG level to capture all messages
        self.logger = get_logger(log_file, "DEBUG")
        
        # Rate limiting
        self.rate_limit_lock = threading.Lock()
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 500ms between requests (2 requests per second) - very conservative for safety
        
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
            'successful_attachments': 0,
            'failed_attachments': 0,
            'orphaned_issues_cleaned': 0
        }
        
        # Atomic operation tracking
        self.atomic_lock = threading.Lock()
        self.pending_issues = {}  # ticket_id -> issue_key for cleanup
        
    def _get_jira_client(self) -> JIRA:
        """
        Get a JIRA client with rate limiting.
        
        Returns:
            JIRA client instance
        """
        with self.rate_limit_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
        
        return JIRA(
            server=f'https://{self.config.domain}',
            basic_auth=(self.config.email, self.config.api_token)
        )
    
    def _extract_failed_field_data(self, ticket_id: int, failed_fields: List[str]) -> str:
        """
        Extract data from failed fields to add to description.
        
        Args:
            ticket_id: Freshdesk ticket ID
            failed_fields: List of failed JIRA field IDs
            
        Returns:
            Formatted string with failed field data
        """
        try:
            # Load ticket data to get field mappings
            ticket_data = self.data_loader.load_ticket_data(ticket_id)
            if not ticket_data['ticket_details']:
                return ""
            
            # Get field mappings
            field_mappings = self.field_mapper.get_field_mappings()
            
            # Reverse lookup: JIRA field ID -> Freshdesk field name
            reverse_mappings = {}
            for fd_field, mapping in field_mappings.items():
                if mapping.get('jira_field'):
                    reverse_mappings[mapping['jira_field']] = fd_field
            
            # Group failed fields by category
            failed_sections = {
                'ticket_fields': [],
                'conversation_fields': [],
                'attachment_fields': [],
                'custom_fields': []
            }
            
            for jira_field in failed_fields:
                fd_field = reverse_mappings.get(jira_field, jira_field)
                
                # Determine category
                category = 'custom_fields'
                if fd_field in ['subject', 'description', 'priority', 'status', 'type']:
                    category = 'ticket_fields'
                elif fd_field.startswith('conversation'):
                    category = 'conversation_fields'
                elif fd_field.startswith('attachment'):
                    category = 'attachment_fields'
                
                # Get field value
                value = ticket_data['ticket_details'].get(fd_field, '')
                if value is None or value == '':
                    value = "N/A"
                
                failed_sections[category].append(f"{fd_field}: {value}")
            
            # Format the failed data
            result = []
            for category, fields in failed_sections.items():
                if fields:
                    category_name = category.replace('_', ' ').title()
                    result.append(f"**— Failed {category_name} —**")
                    result.extend(fields)
                    result.append("")
            
            return "\n".join(result)
            
        except Exception as e:
            self.logger.error(f"Error extracting failed field data: {str(e)}")
            return ""
    
    def _cleanup_orphaned_issue(self, issue_key: str, ticket_id: int) -> bool:
        """
        Clean up an orphaned JIRA issue if migration fails.
        
        Args:
            issue_key: JIRA issue key to delete
            ticket_id: Freshdesk ticket ID for logging
            
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            self.logger.info(f"Cleaning up orphaned issue {issue_key} for ticket {ticket_id}...")
            jira = self._get_jira_client()
            
            # Check if issue exists before trying to delete
            try:
                jira.issue(issue_key)
            except Exception:
                self.logger.warning(f"Issue {issue_key} doesn't exist, skipping cleanup")
                return True  # Consider this a successful cleanup
            
            jira.delete_issue(issue_key)
            self.logger.success(f"Successfully deleted orphaned issue {issue_key}")
            
            with self.stats_lock:
                self.stats['orphaned_issues_cleaned'] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup orphaned issue {issue_key}: {str(e)}")
            return False
    
    def _mark_issue_for_cleanup(self, ticket_id: int, issue_key: str):
        """
        Mark an issue for potential cleanup if migration fails.
        
        Args:
            ticket_id: Freshdesk ticket ID
            issue_key: JIRA issue key
        """
        with self.atomic_lock:
            self.pending_issues[ticket_id] = issue_key
    
    def _remove_cleanup_mark(self, ticket_id: int):
        """
        Remove cleanup mark when migration succeeds.
        
        Args:
            ticket_id: Freshdesk ticket ID
        """
        with self.atomic_lock:
            self.pending_issues.pop(ticket_id, None)
    
    def _cleanup_pending_issues(self):
        """
        Clean up all pending issues that weren't successfully completed.
        """
        with self.atomic_lock:
            pending = self.pending_issues.copy()
            self.pending_issues.clear()
        
        if pending:
            self.logger.info(f"Cleaning up {len(pending)} pending issues...")
            for ticket_id, issue_key in pending.items():
                self._cleanup_orphaned_issue(issue_key, ticket_id)
    
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
        Migrate a single ticket to JIRA with atomic operation support.
        
        Args:
            ticket_id: Freshdesk ticket ID
            dry_run: If True, don't actually create the JIRA issue
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.migration_start(ticket_id)
        
        # Check if ticket is already processed
        existing_status = self.tracker.get_ticket_status(ticket_id)
        if existing_status and existing_status.get('jira_status') in ['success', 'dry_run_completed']:
            self.logger.info(f"Skipping ticket {ticket_id} - already processed (status: {existing_status.get('jira_status')})")
            return True
        
        try:
            # Load ticket data
            self.logger.info(f"Loading ticket data for {ticket_id}...")
            ticket_data = self.data_loader.load_ticket_data(ticket_id)
            
            if not ticket_data['ticket_details']:
                error_msg = f"No ticket details found for ticket {ticket_id}"
                self.logger.error(error_msg)
                self.tracker.update_ticket_status(ticket_id, "failed", reason=error_msg)
                with self.stats_lock:
                    self.stats['failed_migrations'] += 1
                return False
            
            # Convert to JIRA issue
            self.logger.info(f"Converting ticket {ticket_id} to JIRA format...")
            jira_issue = self.ticket_converter.convert_to_jira_issue(
                ticket=ticket_data['ticket_details'],
                conversations=ticket_data['conversations'],
                ticket_attachments=ticket_data['ticket_attachments'],
                conversation_attachments=ticket_data['conversation_attachments'],
                user_data=ticket_data['user_data']
            )
            
            # Set project key and issue type
            self.ticket_converter.set_project_key(jira_issue, self.config.project_key)
            self.ticket_converter.set_issue_type(jira_issue, self.config.issue_type)
            
            if dry_run:
                self.logger.success(f"Dry run - would create issue for ticket {ticket_id}")
                self.tracker.update_ticket_status(ticket_id, "dry_run_completed")
                with self.stats_lock:
                    self.stats['successful_migrations'] += 1
                return True
            
            # Create JIRA issue with atomic operation support
            return self._create_jira_issue_atomic(ticket_id, jira_issue, ticket_data)
            
        except Exception as e:
            error_msg = f"Failed to migrate ticket {ticket_id}: {str(e)}"
            self.logger.error(error_msg)
            
            # Update tracker with failure
            self.tracker.update_ticket_status(ticket_id, "failed", reason=error_msg)
            with self.stats_lock:
                self.stats['failed_migrations'] += 1
            
            return False
    
    def _create_jira_issue_atomic(self, ticket_id: int, jira_issue: Dict[str, Any], ticket_data: Dict[str, Any]) -> bool:
        """
        Create JIRA issue with atomic operation - either complete success or complete failure.
        
        Args:
            ticket_id: Freshdesk ticket ID
            jira_issue: JIRA issue data
            ticket_data: Ticket data for attachments
            
        Returns:
            True if successful, False otherwise
        """
        max_retries = 3
        retry_delay = 2  # seconds
        created_issue = None
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Creating JIRA issue for ticket {ticket_id} (attempt {attempt + 1}/{max_retries})...")
                
                # Try to create the issue
                created_issue = self._create_jira_issue_single_attempt(ticket_id, jira_issue)
                
                # Mark for cleanup in case of failure
                self._mark_issue_for_cleanup(ticket_id, created_issue.key)
                
                # Upload attachments
                attachment_stats = {'total': 0, 'successful': 0, 'failed': 0}
                try:
                    attachment_stats = self._upload_attachments(created_issue.key, ticket_data)
                except Exception as attachment_error:
                    self.logger.error(f"Attachment upload failed for {created_issue.key}: {str(attachment_error)}")
                    # Clean up the issue since attachments failed
                    self._cleanup_orphaned_issue(created_issue.key, ticket_id)
                    # Remove cleanup mark since we already cleaned up
                    self._remove_cleanup_mark(ticket_id)
                    raise attachment_error
                
                # Check if any attachments failed - if so, consider the entire ticket failed
                if attachment_stats['failed'] > 0:
                    failed_msg = f"Attachment upload failed: {attachment_stats['failed']}/{attachment_stats['total']} attachments failed"
                    self.logger.error(f"{failed_msg} for {created_issue.key}")
                    # Clean up the issue since attachments failed
                    self._cleanup_orphaned_issue(created_issue.key, ticket_id)
                    # Remove cleanup mark since we already cleaned up
                    self._remove_cleanup_mark(ticket_id)
                    raise Exception(failed_msg)
                
                # Update tracker with success (atomic with cleanup mark removal)
                try:
                    self.tracker.update_ticket_status(
                        ticket_id, "success", jira_id=created_issue.key,
                        total_attachments=attachment_stats['total'],
                        successful_attachments=attachment_stats['successful'],
                        failed_attachments=attachment_stats['failed'],
                        attachment_type=attachment_stats.get('type', 'none')
                    )
                    # Remove cleanup mark since we succeeded
                    self._remove_cleanup_mark(ticket_id)
                except Exception as tracker_error:
                    self.logger.error(f"Tracker update failed for {created_issue.key}: {str(tracker_error)}")
                    # Clean up the issue since tracker update failed
                    self._cleanup_orphaned_issue(created_issue.key, ticket_id)
                    # Remove cleanup mark since we already cleaned up
                    self._remove_cleanup_mark(ticket_id)
                    raise tracker_error
                
                self.logger.migration_success(ticket_id, created_issue.key)
                with self.stats_lock:
                    self.stats['successful_migrations'] += 1
                
                return True
                
            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"Attempt {attempt + 1}/{max_retries} failed for ticket {ticket_id}: {error_msg}")
                
                # Clean up any created issue
                if created_issue:
                    self._cleanup_orphaned_issue(created_issue.key, ticket_id)
                    created_issue = None
                
                if attempt < max_retries - 1:
                    # Not the last attempt, wait and retry
                    self.logger.info(f"Waiting {retry_delay} seconds before retry...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Last attempt failed, mark as failed
                    final_error_msg = f"Failed to migrate ticket {ticket_id} after {max_retries} attempts: {error_msg}"
                    self.logger.error(final_error_msg)
                    
                    # Update tracker with failure
                    self.tracker.update_ticket_status(ticket_id, "failed", reason=final_error_msg)
                    with self.stats_lock:
                        self.stats['failed_migrations'] += 1
                    
                    return False
        
        return False
    
    def _create_jira_issue_single_attempt(self, ticket_id: int, jira_issue: Dict[str, Any]):
        """
        Single attempt to create JIRA issue with field mapping error handling.
        
        Args:
            ticket_id: Freshdesk ticket ID
            jira_issue: JIRA issue data
            
        Returns:
            JIRA issue object if successful
            
        Raises:
            Exception if creation fails
        """
        try:
            jira = self._get_jira_client()
            issue = jira.create_issue(fields=jira_issue['fields'])
            self.logger.success(f"Successfully created JIRA issue: {issue.key}")
            return issue
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"JIRA API error for ticket {ticket_id}: {error_msg}")
            
            # Parse JIRA API error to extract problematic field IDs
            import re
            field_pattern = r'customfield_\d+'
            failed_fields = re.findall(field_pattern, error_msg)
            
            if failed_fields and ("cannot be set" in error_msg or "field" in error_msg.lower()):
                self.logger.info(f"Attempting to handle field mapping failure for ticket {ticket_id}...")
                self.logger.info(f"Identified failed fields: {failed_fields}")
                
                # Remove failed fields from JIRA issue
                for field_id in failed_fields:
                    if field_id in jira_issue['fields']:
                        del jira_issue['fields'][field_id]
                        self.logger.info(f"Removed failed field: {field_id}")
                
                # Add failed fields to description
                failed_data = self._extract_failed_field_data(ticket_id, failed_fields)
                if failed_data:
                    current_description = jira_issue['fields'].get('description', '')
                    new_description = current_description + '\n\n' + failed_data
                    jira_issue['fields']['description'] = new_description
                    self.logger.info(f"Added failed fields to description")
                
                # Retry creating the issue with fixed fields
                try:
                    self.logger.info(f"Retrying JIRA issue creation for ticket {ticket_id}...")
                    jira = self._get_jira_client()
                    issue = jira.create_issue(fields=jira_issue['fields'])
                    self.logger.success(f"Successfully created JIRA issue after field mapping fix: {issue.key}")
                    return issue
                    
                except Exception as retry_e:
                    retry_error_msg = str(retry_e)
                    self.logger.error(f"Failed to create JIRA issue after field mapping fix for ticket {ticket_id}: {retry_error_msg}")
                    raise retry_e
            else:
                # Not a field mapping error, re-raise
                raise e
    
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
            self.logger.error(error_msg)
            
            # Update tracker with failure
            self.tracker.update_ticket_status(ticket_id, "failed", reason=error_msg)
            
            with self.stats_lock:
                self.stats['failed_migrations'] += 1
            
            return (ticket_id, False)
    
    def _upload_attachments(self, issue_key: str, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload attachments for a ticket.
        
        Args:
            issue_key: JIRA issue key
            ticket_data: Ticket data dictionary
            
        Returns:
            Dictionary with attachment statistics: {'total': int, 'successful': int, 'failed': int}
        """
        # Initialize attachment statistics
        total_attachments = 0
        successful_attachments = 0
        failed_attachments = 0
        
        # Validate ticket_data structure
        if not isinstance(ticket_data, dict):
            self.logger.warning(f"Invalid ticket_data type for {issue_key}: {type(ticket_data)}")
            return {'total': 0, 'successful': 0, 'failed': 0}
        
        ticket_id = ticket_data.get('ticket_id')
        if ticket_id is None:
            self.logger.warning(f"Missing ticket_id in ticket_data for {issue_key}")
            return {'total': 0, 'successful': 0, 'failed': 0}
        
        ticket_attachments = ticket_data.get('ticket_attachments', [])
        conversation_attachments = ticket_data.get('conversation_attachments', [])
        
        # Upload ticket attachments
        if ticket_attachments:
            self.logger.info(f"Uploading {len(ticket_attachments)} ticket attachments...")
            attachment_data = []
            
            for attachment in ticket_attachments:
                filename = attachment.get('name', '')
                attachment_id = attachment.get('id', '')
                file_path = self.data_loader.get_attachment_file_path(ticket_id, filename, attachment_id)
                if file_path:
                    attachment_data.append({
                        'file_path': file_path,
                        'attachment_id': attachment_id,
                        'original_name': filename
                    })
            
            if attachment_data:
                results = self.bulk_uploader.upload_attachments_with_renaming(issue_key, attachment_data)
                successful = sum(results)
                failed = len(attachment_data) - successful
                
                total_attachments += len(attachment_data)
                successful_attachments += successful
                failed_attachments += failed
                
                self.logger.info(f"Uploaded {successful}/{len(attachment_data)} ticket attachments")
                
                with self.stats_lock:
                    self.stats['total_attachments'] += len(attachment_data)
                    self.stats['successful_attachments'] += successful
                    self.stats['failed_attachments'] += failed
        else:
            self.logger.warning("No valid ticket attachment files found")
        
        # Upload conversation attachments
        if conversation_attachments:
            self.logger.info(f"Uploading {len(conversation_attachments)} conversation attachments...")
            attachment_data = []
            
            for attachment in conversation_attachments:
                filename = attachment.get('name', '')
                attachment_id = attachment.get('id', '')
                file_path = self.data_loader.get_attachment_file_path(ticket_id, filename, attachment_id)
                if file_path:
                    attachment_data.append({
                        'file_path': file_path,
                        'attachment_id': attachment_id,
                        'original_name': filename
                    })
            
            if attachment_data:
                results = self.bulk_uploader.upload_attachments_with_renaming(issue_key, attachment_data)
                successful = sum(results)
                failed = len(attachment_data) - successful
                
                total_attachments += len(attachment_data)
                successful_attachments += successful
                failed_attachments += failed
                
                self.logger.info(f"Uploaded {successful}/{len(attachment_data)} conversation attachments")
                
                with self.stats_lock:
                    self.stats['total_attachments'] += len(attachment_data)
                    self.stats['successful_attachments'] += successful
                    self.stats['failed_attachments'] += failed
        else:
            self.logger.warning("No valid conversation attachment files found")
        
        # Log attachment summary for this ticket
        if total_attachments > 0:
            self.logger.attachment_upload(ticket_id, total_attachments, successful_attachments)
        
        # Determine attachment type
        has_ticket_attachments = len(ticket_attachments) > 0
        has_conversation_attachments = len(conversation_attachments) > 0
        
        if has_ticket_attachments and has_conversation_attachments:
            attachment_type = 'mixed'
        elif has_conversation_attachments:
            attachment_type = 'conversation'
        elif has_ticket_attachments:
            attachment_type = 'attachment'
        else:
            attachment_type = 'none'
        
        return {
            'total': total_attachments,
            'successful': successful_attachments,
            'failed': failed_attachments,
            'type': attachment_type
        }
    
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
        
        try:
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
        except KeyboardInterrupt:
            self.logger.warning("Migration interrupted by user. Cleaning up pending issues...")
            self._cleanup_pending_issues()
            raise
        except Exception as e:
            self.logger.error("Migration failed. Cleaning up pending issues...")
            self._cleanup_pending_issues()
            raise
        
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
            'failed_attachments': self.stats['failed_attachments'],
            'attachment_success_rate': self.stats['successful_attachments'] / self.stats['total_attachments'] if self.stats['total_attachments'] > 0 else 0,
            'orphaned_issues_cleaned': self.stats['orphaned_issues_cleaned'],
            'tracker_summary': tracker_summary
        }
        
        # Log summary
        self.logger.summary(summary)
        
        return summary


def main():
    """Main function for the migration script."""
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Generate default log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_log_file = logs_dir / f"migration_{timestamp}.log"
    
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
        log_file = args.log_file if args.log_file else str(default_log_file)
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
        log_file = os.getenv('LOG_FILE', str(default_log_file))
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
        
        # Log the log file location
        if log_file:
            print(f"📝 Migration logs will be saved to: {log_file}")
        
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
        try:
            summary = migrator.migrate_tickets(ticket_ids, dry_run, parallel=not sequential)
            
            # Clean up any remaining pending issues
            migrator._cleanup_pending_issues()
            
            # Summary is already logged by the logger
        except KeyboardInterrupt:
            migrator.logger.warning("Migration interrupted by user. Cleaning up...")
            migrator._cleanup_pending_issues()
            sys.exit(1)
        
    except Exception as e:
        # Try to get logger if available, otherwise use print
        try:
            migrator.logger.error(f"Migration failed: {e}")
        except:
            print(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
