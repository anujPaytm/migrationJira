#!/usr/bin/env python3
"""
Inspect JIRA Issue Script - Check what was actually stored in JIRA
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

def inspect_jira_issue(issue_key: str):
    """Inspect a JIRA issue and show all field values"""
    
    # Initialize JIRA client
    config = JiraConfig()
    
    jira = JIRA(
        server=f"https://{config.domain}",
        basic_auth=(config.email, config.api_token)
    )
    
    print(f"Fetching JIRA issue: {issue_key}")
    print("=" * 80)
    
    try:
        # Get the issue with all fields
        issue = jira.issue(issue_key, expand='names')
        
        print(f"Issue: {issue.key}")
        print(f"Summary: {issue.fields.summary}")
        print(f"Status: {issue.fields.status}")
        print(f"Created: {issue.fields.created}")
        print(f"Updated: {issue.fields.updated}")
        print()
        
        print("CUSTOM FIELDS:")
        print("-" * 40)
        
        # Get all field names
        field_names = jira._get_json('field')
        field_name_map = {field['id']: field['name'] for field in field_names}
        
        # Check specific custom fields we're interested in
        important_fields = [
            'customfield_10289',  # FD_Priority
            'customfield_10290',  # FD_Created_At
            'customfield_10291',  # FD_Updated_At
            'customfield_10292',  # FD_Reporter
            'customfield_10293',  # FD_Assignee
            'customfield_10294',  # FD_Status
            'customfield_10295',  # FD_IssueType
            'customfield_10322',  # FD_CC_Emails
            'customfield_10323',  # FD_FWD_Emails
            'customfield_10324',  # FD_Reply_CC_Emails
            'customfield_10325',  # FD_Ticket_CC_Emails
            'customfield_10326',  # FD_Ticket_BCC_Emails
            'customfield_10327',  # FD_FR_Escalated
            'customfield_10328',  # FD_Spam
            'customfield_10329',  # FD_Email_Config_ID
            'customfield_10330',  # FD_Group_ID
            'customfield_10333',  # FD_Source
            'customfield_10334',  # FD_Company_ID
            'customfield_10335',  # FD_Association_Type
            'customfield_10336',  # FD_Support_Email
            'customfield_10337',  # FD_To_Emails
            'customfield_10338',  # FD_Product_ID
            'customfield_10339',  # FD_Ticket_ID
            'customfield_10342',  # FD_Due_By
            'customfield_10343',  # FD_FR_Due_By
            'customfield_10344',  # FD_Is_Escalated
            'customfield_10345',  # FD_Tags
            'customfield_10346',  # FD_Source_Additional_Info
            'customfield_10347',  # FD_Structured_Description
            'customfield_10348',  # FD_Sentiment_Score
            'customfield_10349',  # FD_Initial_Sentiment_Score
            'customfield_10350',  # FD_NR_Due_By
            'customfield_10351',  # FD_NR_Escalated
            'customfield_10352',  # FD_Conversation_Details
            'customfield_10353',  # FD_Attachment_Details
            'customfield_10354',  # FD_Custom_Fields
        ]
        
        for field_id in important_fields:
            field_name = field_name_map.get(field_id, field_id)
            field_value = getattr(issue.fields, field_id, None)
            
            print(f"{field_name} ({field_id}):")
            if field_value is None:
                print("  Value: None")
            elif field_value == "":
                print("  Value: (empty string)")
            else:
                # Truncate long values for readability
                value_str = str(field_value)
                if len(value_str) > 200:
                    print(f"  Value: {value_str[:200]}... [TRUNCATED]")
                    print(f"  Full Length: {len(value_str)} characters")
                else:
                    print(f"  Value: {value_str}")
            print()
        
        print("DESCRIPTION:")
        print("-" * 40)
        if hasattr(issue.fields, 'description') and issue.fields.description:
            desc = issue.fields.description
            if len(desc) > 500:
                print(f"{desc[:500]}... [TRUNCATED]")
                print(f"Full Length: {len(desc)} characters")
            else:
                print(desc)
        else:
            print("No description")
            
    except Exception as e:
        print(f"Error fetching issue: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 inspect_jira_issue.py <issue_key>")
        print("Example: python3 inspect_jira_issue.py FTJM-50")
        sys.exit(1)
    
    issue_key = sys.argv[1]
    inspect_jira_issue(issue_key)
