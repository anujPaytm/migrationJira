#!/usr/bin/env python3
"""
Get full field content without truncation
"""

import sys
import os
import json

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

try:
    from jira import JIRA
except ImportError:
    print("Error: python-jira package not installed. Run: pip install python-jira")
    sys.exit(1)


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


def get_full_field_content(issue_key: str, field_id: str):
    """Get full content of a specific field without truncation"""
    
    # Initialize JIRA client
    config = JiraConfig()
    
    jira = JIRA(
        server=f"https://{config.domain}",
        basic_auth=(config.email, config.api_token)
    )
    
    print(f"Fetching full content for field {field_id} in issue: {issue_key}")
    print("=" * 80)
    
    try:
        # Get the issue with all fields
        issue = jira.issue(issue_key, expand='names')
        
        # Get the field value
        field_value = getattr(issue.fields, field_id, None)
        
        if field_value is None:
            print(f"Field {field_id} is None")
        elif field_value == "":
            print(f"Field {field_id} is empty string")
        else:
            print(f"Full content of {field_id}:")
            print("-" * 40)
            print(field_value)
            print("-" * 40)
            print(f"Content length: {len(str(field_value))} characters")
            
    except Exception as e:
        print(f"Error fetching issue: {e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 get_full_field_content.py <issue_key> <field_id>")
        print("Example: python3 get_full_field_content.py FTJM-51 customfield_10352")
        sys.exit(1)
    
    issue_key = sys.argv[1]
    field_id = sys.argv[2]
    get_full_field_content(issue_key, field_id)
