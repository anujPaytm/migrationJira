#!/usr/bin/env python3
"""
Utility script to identify and clean up orphaned JIRA issues.
Orphaned issues are those that exist in JIRA but are not tracked in the migration tracker.
"""

import os
import sys
import argparse
import requests
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Set, Dict, Any

# Load environment variables
load_dotenv()

# Add project root and src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Ensure the src directory is treated as a Python package
src_path = project_root / "src"
if not (src_path / "__init__.py").exists():
    (src_path / "__init__.py").touch()

from utils.tracker import MigrationTracker

class OrphanedIssueCleaner:
    """Utility to identify and clean up orphaned JIRA issues."""
    
    def __init__(self):
        """Initialize the cleaner with JIRA credentials."""
        self.domain = os.getenv('JIRA_DOMAIN')
        self.email = os.getenv('JIRA_EMAIL')
        self.api_token = os.getenv('JIRA_API_TOKEN')
        self.project_key = os.getenv('JIRA_PROJECT_KEY', 'FTJM')
        
        if not all([self.domain, self.email, self.api_token]):
            raise ValueError("Missing required JIRA environment variables")
        
        self.base_url = f'https://{self.domain}/rest/api/3'
        self.auth = (self.email, self.api_token)
        self.tracker = MigrationTracker()
    
    def get_all_jira_issues_in_range(self, start_key: str, end_key: str) -> List[Dict[str, Any]]:
        """Get all JIRA issues in a specific range."""
        all_issues = []
        start_at = 0
        max_results = 1000
        
        print(f"Fetching all issues in range {start_key} to {end_key}...")
        
        while True:
            try:
                response = requests.get(
                    f'{self.base_url}/search',
                    params={
                        'jql': f'project = {self.project_key} AND key >= {start_key} AND key <= {end_key} ORDER BY key ASC',
                        'startAt': start_at,
                        'maxResults': max_results,
                        'fields': 'key,summary,created,updated,reporter,assignee,status,issuetype'
                    },
                    auth=self.auth,
                    timeout=60
                )
                response.raise_for_status()
                data = response.json()
                
                issues = data['issues']
                if not issues:
                    break
                
                all_issues.extend(issues)
                print(f"Fetched {len(all_issues)} issues so far...")
                
                if len(issues) < max_results:
                    break
                
                start_at += max_results
                
            except Exception as e:
                print(f"Error fetching issues: {e}")
                break
        
        return all_issues
    
    def get_tracked_issues(self) -> Set[str]:
        """Get all JIRA issue keys that are tracked in the migration tracker."""
        try:
            df = pd.read_csv('tracker/migration_tracker.csv')
            successful_issues = df[df['jira_status'] == 'success']['jira_id'].dropna().tolist()
            return set(successful_issues)
        except Exception as e:
            print(f"Error reading tracker: {e}")
            return set()
    
    def find_orphaned_issues(self, start_key: str = None, end_key: str = None) -> List[Dict[str, Any]]:
        """
        Find orphaned issues (in JIRA but not in tracker).
        
        Args:
            start_key: Start JIRA key (e.g., 'FTJM-18074')
            end_key: End JIRA key (e.g., 'FTJM-32956')
            
        Returns:
            List of orphaned issue dictionaries
        """
        # Get tracked issues
        tracked_issues = self.get_tracked_issues()
        print(f"Found {len(tracked_issues)} tracked issues in migration tracker")
        
        # Get JIRA issues in range
        if not start_key:
            start_key = f"{self.project_key}-18074"
        if not end_key:
            end_key = f"{self.project_key}-32956"
        
        jira_issues = self.get_all_jira_issues_in_range(start_key, end_key)
        print(f"Found {len(jira_issues)} issues in JIRA range {start_key} to {end_key}")
        
        # Find orphaned issues
        jira_keys = {issue['key'] for issue in jira_issues}
        orphaned_keys = jira_keys - tracked_issues
        
        orphaned_issues = [issue for issue in jira_issues if issue['key'] in orphaned_keys]
        
        print(f"Found {len(orphaned_issues)} orphaned issues")
        return orphaned_issues
    
    def analyze_orphaned_issues(self, orphaned_issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze orphaned issues by various criteria."""
        if not orphaned_issues:
            return {}
        
        analysis = {
            'total_count': len(orphaned_issues),
            'by_date': {},
            'by_type': {},
            'by_status': {},
            'sample_issues': []
        }
        
        # Group by creation date
        for issue in orphaned_issues:
            created = issue['fields']['created'][:10]  # YYYY-MM-DD
            if created not in analysis['by_date']:
                analysis['by_date'][created] = []
            analysis['by_date'][created].append(issue)
        
        # Group by issue type
        for issue in orphaned_issues:
            issue_type = issue['fields']['issuetype']['name']
            if issue_type not in analysis['by_type']:
                analysis['by_type'][issue_type] = []
            analysis['by_type'][issue_type].append(issue)
        
        # Group by status
        for issue in orphaned_issues:
            status = issue['fields']['status']['name']
            if status not in analysis['by_status']:
                analysis['by_status'][status] = []
            analysis['by_status'][status].append(issue)
        
        # Sample issues
        analysis['sample_issues'] = orphaned_issues[:10]
        
        return analysis
    
    def delete_orphaned_issue(self, issue_key: str) -> bool:
        """Delete a single orphaned issue."""
        try:
            print(f"🧹 Deleting orphaned issue {issue_key}...")
            response = requests.delete(
                f'{self.base_url}/issue/{issue_key}',
                auth=self.auth,
                timeout=30
            )
            response.raise_for_status()
            print(f"✅ Successfully deleted {issue_key}")
            return True
        except Exception as e:
            print(f"❌ Failed to delete {issue_key}: {e}")
            return False
    
    def cleanup_orphaned_issues(self, orphaned_issues: List[Dict[str, Any]], dry_run: bool = True) -> Dict[str, int]:
        """
        Clean up orphaned issues.
        
        Args:
            orphaned_issues: List of orphaned issue dictionaries
            dry_run: If True, only show what would be deleted
            
        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            'total_orphaned': len(orphaned_issues),
            'deleted': 0,
            'failed': 0
        }
        
        if dry_run:
            print(f"🔍 DRY RUN: Would delete {len(orphaned_issues)} orphaned issues")
            print("Sample issues that would be deleted:")
            for issue in orphaned_issues[:5]:
                created = issue['fields']['created'][:10]
                summary = issue['fields']['summary'][:60]
                print(f"  {issue['key']}: {summary}... (created: {created})")
            return stats
        
        print(f"🧹 Starting cleanup of {len(orphaned_issues)} orphaned issues...")
        
        for i, issue in enumerate(orphaned_issues, 1):
            print(f"Progress: {i}/{len(orphaned_issues)}")
            
            if self.delete_orphaned_issue(issue['key']):
                stats['deleted'] += 1
            else:
                stats['failed'] += 1
        
        print(f"✅ Cleanup completed: {stats['deleted']} deleted, {stats['failed']} failed")
        return stats


def main():
    """Main function for the orphaned issue cleanup script."""
    parser = argparse.ArgumentParser(description='Identify and clean up orphaned JIRA issues')
    parser.add_argument('--start-key', help='Start JIRA key (e.g., FTJM-18074)')
    parser.add_argument('--end-key', help='End JIRA key (e.g., FTJM-32956)')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze, don\'t delete')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    parser.add_argument('--delete-all', action='store_true', help='Delete all orphaned issues (use with caution!)')
    
    args = parser.parse_args()
    
    try:
        cleaner = OrphanedIssueCleaner()
        
        # Find orphaned issues
        orphaned_issues = cleaner.find_orphaned_issues(args.start_key, args.end_key)
        
        if not orphaned_issues:
            print("✅ No orphaned issues found!")
            return
        
        # Analyze orphaned issues
        analysis = cleaner.analyze_orphaned_issues(orphaned_issues)
        
        print(f"\n=== Orphaned Issues Analysis ===")
        print(f"Total orphaned issues: {analysis['total_count']}")
        
        if analysis['by_date']:
            print("\nBy creation date:")
            for date in sorted(analysis['by_date'].keys()):
                count = len(analysis['by_date'][date])
                print(f"  {date}: {count} issues")
        
        if analysis['by_type']:
            print("\nBy issue type:")
            for issue_type, issues in analysis['by_type'].items():
                print(f"  {issue_type}: {len(issues)} issues")
        
        if analysis['by_status']:
            print("\nBy status:")
            for status, issues in analysis['by_status'].items():
                print(f"  {status}: {len(issues)} issues")
        
        print(f"\nSample orphaned issues:")
        for issue in analysis['sample_issues']:
            created = issue['fields']['created'][:10]
            summary = issue['fields']['summary'][:60]
            print(f"  {issue['key']}: {summary}... (created: {created})")
        
        # Handle cleanup
        if args.delete_all:
            if args.dry_run:
                cleaner.cleanup_orphaned_issues(orphaned_issues, dry_run=True)
            else:
                print(f"\n⚠️ WARNING: You are about to delete {len(orphaned_issues)} orphaned issues!")
                confirm = input("Type 'YES' to confirm: ")
                if confirm == 'YES':
                    stats = cleaner.cleanup_orphaned_issues(orphaned_issues, dry_run=False)
                    print(f"\n=== Cleanup Summary ===")
                    print(f"Total orphaned: {stats['total_orphaned']}")
                    print(f"Successfully deleted: {stats['deleted']}")
                    print(f"Failed to delete: {stats['failed']}")
                else:
                    print("Cleanup cancelled.")
        elif not args.analyze_only:
            print(f"\nTo delete orphaned issues, use --delete-all")
            print(f"To see what would be deleted, use --delete-all --dry-run")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
