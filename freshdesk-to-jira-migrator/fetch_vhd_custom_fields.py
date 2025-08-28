#!/usr/bin/env python3
"""
Script to fetch custom fields from VHD Jira project and display their mappings.
"""

import os
import sys
import json
from dotenv import load_dotenv
from jira import JIRA

# Load environment variables
load_dotenv()

def fetch_custom_fields():
    """Fetch all custom fields from Jira and display their mappings."""
    
    # Jira configuration from .env
    domain = os.getenv('JIRA_DOMAIN')
    email = os.getenv('JIRA_EMAIL')
    api_token = os.getenv('JIRA_API_TOKEN')
    project_key = os.getenv('JIRA_PROJECT_KEY')
    
    if not all([domain, email, api_token, project_key]):
        print("❌ Missing required environment variables")
        return
    
    try:
        # Connect to Jira with working authentication method
        jira = JIRA(server=f'https://{domain}', basic_auth=(email, api_token.strip()))
        print(f"✅ Connected to Jira: {domain}")
        print(f"📋 Project: {project_key}")
        print()
        
        # First check if project exists
        try:
            project = jira.project(project_key)
            print(f"✅ Project found: {project.name}")
        except Exception as e:
            print(f"❌ Project '{project_key}' not found: {e}")
            print("🔍 Available projects:")
            projects = jira.projects()
            for proj in projects:
                print(f"  • {proj.key} - {proj.name}")
            return None
        
        # Fetch all custom fields
        print("🔍 Fetching all custom fields...")
        custom_fields = jira.fields()
        
        # Filter and organize custom fields
        field_mappings = {}
        
        for field in custom_fields:
            if field['custom']:
                field_id = field['id']
                field_name = field['name']
                field_type = field.get('schema', {}).get('type', 'unknown')
                
                field_mappings[field_id] = {
                    'name': field_name,
                    'type': field_type,
                    'custom': True
                }
        
        # Display results
        print(f"📊 Found {len(field_mappings)} custom fields:")
        print("=" * 80)
        
        # Sort by field ID for easier reading
        sorted_fields = sorted(field_mappings.items(), key=lambda x: x[0])
        
        for field_id, field_info in sorted_fields:
            print(f"{field_id:<20} | {field_info['name']:<30} | {field_info['type']}")
        
        print("=" * 80)
        
        # Save to file for reference
        output_file = f"vhd_custom_fields_{project_key}.json"
        with open(output_file, 'w') as f:
            json.dump(field_mappings, f, indent=2)
        
        print(f"💾 Field mappings saved to: {output_file}")
        
        # Also save in a more readable format
        readable_file = f"vhd_custom_fields_{project_key}_readable.txt"
        with open(readable_file, 'w') as f:
            f.write(f"Custom Fields for Project: {project_key}\n")
            f.write("=" * 80 + "\n\n")
            for field_id, field_info in sorted_fields:
                f.write(f"{field_id:<20} | {field_info['name']:<30} | {field_info['type']}\n")
        
        print(f"📝 Readable format saved to: {readable_file}")
        
        return field_mappings
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    fetch_custom_fields()
