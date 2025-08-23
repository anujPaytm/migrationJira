#!/usr/bin/env python3
"""
Delete JIRA tickets in batches with parallel processing.
Supports deleting all tickets after a specific issue key (e.g., FTJM-64).
"""

import os
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from jira import JIRA
from dotenv import load_dotenv

load_dotenv()

# Add project root and src to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.logger import get_logger

class JiraTicketDeleter:
    """
    Deletes JIRA tickets in parallel batches.
    """
    
    def __init__(self, max_workers: int = 10, log_file: str = None):
        """
        Initialize the JIRA ticket deleter.
        
        Args:
            max_workers: Maximum number of parallel workers for deletion
            log_file: Path to log file (optional)
        """
        self.max_workers = max_workers
        self.logger = get_logger(log_file, "INFO")
        self.jira = self._get_jira_client()
        self.project_key = os.getenv('JIRA_PROJECT_KEY', 'FTJM')
        
    def _get_jira_client(self) -> JIRA:
        """Get authenticated JIRA client."""
        domain = os.getenv('JIRA_DOMAIN')
        email = os.getenv('JIRA_EMAIL')
        api_token = os.getenv('JIRA_API_TOKEN')
        
        if not all([domain, email, api_token]):
            raise ValueError("Missing required JIRA environment variables")
        
        return JIRA(
            server=f"https://{domain}",
            basic_auth=(email, api_token)
        )
    
    def get_issues_after_key(self, after_key: str, batch_size: int = 100) -> List[str]:
        """
        Get all issue keys after a specific issue key.
        
        Args:
            after_key: Issue key to start after (e.g., 'FTJM-64')
            batch_size: Number of issues to fetch per batch
            
        Returns:
            List of issue keys to delete
        """
        self.logger.info(f"Finding all issues after {after_key}...")
        
        # Extract the number from the after_key
        try:
            after_number = int(after_key.split('-')[1])
        except (IndexError, ValueError):
            raise ValueError(f"Invalid issue key format: {after_key}")
        
        # Search for issues with key greater than after_key
        jql = f"project = {self.project_key} AND key > {after_key} ORDER BY key ASC"
        
        all_issues = []
        start_at = 0
        
        while True:
            try:
                issues = self.jira.search_issues(
                    jql, 
                    startAt=start_at, 
                    maxResults=batch_size,
                    fields='key'
                )
                
                if not issues:
                    break
                
                issue_keys = [issue.key for issue in issues]
                all_issues.extend(issue_keys)
                
                self.logger.info(f"Found batch: {len(issue_keys)} issues (total: {len(all_issues)})")
                
                if len(issues) < batch_size:
                    break
                
                start_at += batch_size
                
            except Exception as e:
                self.logger.error(f"Error fetching issues: {str(e)}")
                break
        
        self.logger.info(f"Found {len(all_issues)} issues to delete after {after_key}")
        return all_issues
    
    def get_all_project_issues(self, batch_size: int = 100) -> List[str]:
        """
        Get all issue keys in the project.
        
        Args:
            batch_size: Number of issues to fetch per batch
            
        Returns:
            List of all issue keys in the project
        """
        self.logger.info(f"Finding all issues in project {self.project_key}...")
        
        jql = f"project = {self.project_key} ORDER BY key ASC"
        
        all_issues = []
        start_at = 0
        
        while True:
            try:
                issues = self.jira.search_issues(
                    jql, 
                    startAt=start_at, 
                    maxResults=batch_size,
                    fields='key'
                )
                
                if not issues:
                    break
                
                issue_keys = [issue.key for issue in issues]
                all_issues.extend(issue_keys)
                
                self.logger.info(f"Found batch: {len(issue_keys)} issues (total: {len(all_issues)})")
                
                if len(issues) < batch_size:
                    break
                
                start_at += batch_size
                
            except Exception as e:
                self.logger.error(f"Error fetching issues: {str(e)}")
                break
        
        self.logger.info(f"Found {len(all_issues)} total issues in project")
        return all_issues
    
    def delete_issue_batch(self, issue_keys: List[str]) -> int:
        """
        Delete a batch of issues in parallel.
        
        Args:
            issue_keys: List of issue keys to delete
            
        Returns:
            Number of successfully deleted issues
        """
        if not issue_keys:
            return 0
        
        self.logger.info(f"Deleting batch of {len(issue_keys)} issues...")
        
        successful_deletions = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit deletion tasks
            future_to_key = {
                executor.submit(self._delete_single_issue, key): key 
                for key in issue_keys
            }
            
            # Process results
            for future in as_completed(future_to_key):
                issue_key = future_to_key[future]
                try:
                    success = future.result()
                    if success:
                        successful_deletions += 1
                        self.logger.info(f"Deleted: {issue_key}")
                    else:
                        self.logger.error(f"Failed to delete: {issue_key}")
                except Exception as e:
                    self.logger.error(f"Error deleting {issue_key}: {str(e)}")
        
        self.logger.info(f"Batch complete: {successful_deletions}/{len(issue_keys)} deleted")
        return successful_deletions
    
    def _delete_single_issue(self, issue_key: str) -> bool:
        """
        Delete a single JIRA issue.
        
        Args:
            issue_key: Issue key to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add small delay to avoid overwhelming the API
            time.sleep(0.1)  # 100ms delay per worker
            
            issue = self.jira.issue(issue_key)
            issue.delete()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete {issue_key}: {str(e)}")
            return False
    
    def delete_issues_in_batches(self, issue_keys: List[str], batch_size: int = 100, 
                                auto_confirm: bool = False) -> int:
        """
        Delete issues in batches with confirmation.
        
        Args:
            issue_keys: List of issue keys to delete
            batch_size: Number of issues per batch
            auto_confirm: If True, skip confirmation prompts
            
        Returns:
            Total number of successfully deleted issues
        """
        if not issue_keys:
            self.logger.info("No issues to delete.")
            return 0
        
        self.logger.info(f"Planning to delete {len(issue_keys)} issues in batches of {batch_size}")
        self.logger.info(f"Using {self.max_workers} parallel workers per batch")
        
        if not auto_confirm:
            confirm = input(f"\n⚠️  Are you sure you want to delete {len(issue_keys)} issues? (yes/no): ")
            if confirm.lower() != 'yes':
                self.logger.info("Deletion cancelled.")
                return 0
        
        total_deleted = 0
        
        # Process in batches
        for i in range(0, len(issue_keys), batch_size):
            batch = issue_keys[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(issue_keys) + batch_size - 1) // batch_size
            
            self.logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} issues)")
            self.logger.info(f"Range: {batch[0]} to {batch[-1]}")
            
            if not auto_confirm:
                confirm = input(f"Delete this batch? (yes/no/all): ")
                if confirm.lower() == 'no':
                    self.logger.info("Skipping this batch.")
                    continue
                elif confirm.lower() == 'all':
                    auto_confirm = True
                elif confirm.lower() != 'yes':
                    self.logger.error("Invalid input. Skipping batch.")
                    continue
            
            batch_deleted = self.delete_issue_batch(batch)
            total_deleted += batch_deleted
            
            self.logger.info(f"Progress: {total_deleted}/{len(issue_keys)} total deleted")
            
            # Small delay between batches
            if i + batch_size < len(issue_keys):
                self.logger.info("Waiting 2 seconds before next batch...")
                time.sleep(2)
        
        self.logger.info(f"Deletion complete! {total_deleted}/{len(issue_keys)} issues deleted.")
        return total_deleted


def main():
    """Main function for the deletion script."""
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Generate default log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_log_file = logs_dir / f"deletion_{timestamp}.log"
    
    parser = argparse.ArgumentParser(description='Delete JIRA tickets in batches')
    parser.add_argument('--after-key', help='Delete all issues after this key (e.g., FTJM-64)')
    parser.add_argument('--all', action='store_true', help='Delete all issues in the project')
    parser.add_argument('--batch-size', type=int, default=100, help='Number of issues per batch (default: 100)')
    parser.add_argument('--workers', type=int, default=10, help='Number of parallel workers (default: 10)')
    parser.add_argument('--auto-confirm', action='store_true', help='Skip confirmation prompts')
    parser.add_argument('--log-file', help='Path to log file (optional)')
    
    args = parser.parse_args()
    
    if not args.after_key and not args.all:
        print("❌ Error: Must specify either --after-key or --all")
        sys.exit(1)
    
    # Use provided log file or default
    log_file = args.log_file if args.log_file else str(default_log_file)
    
    try:
        deleter = JiraTicketDeleter(max_workers=args.workers, log_file=log_file)
        
        # Log the log file location
        print(f"📝 Deletion logs will be saved to: {log_file}")
        
        if args.after_key:
            issue_keys = deleter.get_issues_after_key(args.after_key, args.batch_size)
        else:
            issue_keys = deleter.get_all_project_issues(args.batch_size)
        
        if issue_keys:
            deleter.delete_issues_in_batches(
                issue_keys, 
                batch_size=args.batch_size,
                auto_confirm=args.auto_confirm
            )
        else:
            print("ℹ️  No issues found to delete.")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
