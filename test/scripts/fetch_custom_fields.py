#!/usr/bin/env python3
"""
Fetch JIRA Custom Fields Script
"""

import sys
import os
import json
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.jira_config import JiraConfig

try:
    from jira import JIRA
except ImportError:
    print("Error: python-jira package not installed. Run: pip install python-jira")
    sys.exit(1)

def fetch_custom_fields():
    """Fetch all custom fields from JIRA"""
    
    # Initialize JIRA client
    config = JiraConfig()
    config.validate()
    
    jira = JIRA(
        options=config.get_jira_options(),
        basic_auth=config.get_auth()
    )
    
    print("Fetching custom fields from JIRA...")
    
    try:
        # Get all custom fields
        custom_fields = jira.fields()
        
        # Filter only custom fields (they start with 'customfield_')
        jira_custom_fields = []
        
        for field in custom_fields:
            if field['id'].startswith('customfield_'):
                field_info = {
                    'id': field['id'],
                    'name': field['name'],
                    'type': field.get('schema', {}).get('type', 'unknown'),
                    'custom': field.get('custom', False),
                    'searchable': field.get('searchable', False),
                    'orderable': field.get('orderable', False),
                    'navigable': field.get('navigable', False),
                    'clauseNames': field.get('clauseNames', []),
                    'scope': field.get('scope', {})
                }
                jira_custom_fields.append(field_info)
        
        # Sort by field ID for easier reading
        jira_custom_fields.sort(key=lambda x: x['id'])
        
        print(f"Found {len(jira_custom_fields)} custom fields:")
        print("=" * 80)
        
        for field in jira_custom_fields:
            print(f"ID: {field['id']}")
            print(f"Name: {field['name']}")
            print(f"Type: {field['type']}")
            print(f"Custom: {field['custom']}")
            print(f"Searchable: {field['searchable']}")
            print(f"Orderable: {field['orderable']}")
            print(f"Navigable: {field['navigable']}")
            if field['clauseNames']:
                print(f"Clause Names: {', '.join(field['clauseNames'])}")
            print("-" * 40)
        
        # Save to JSON file
        output_file = 'jira_custom_fields.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(jira_custom_fields, f, indent=2, ensure_ascii=False)
        
        print(f"\nCustom fields saved to: {output_file}")
        
        # Also create a mapping file for easy reference
        mapping_file = 'custom_field_mapping.txt'
        with open(mapping_file, 'w', encoding='utf-8') as f:
            f.write("JIRA Custom Fields Mapping\n")
            f.write("=" * 50 + "\n\n")
            f.write("Format: customfield_XXXXX | Field Name | Type\n")
            f.write("-" * 50 + "\n")
            
            for field in jira_custom_fields:
                f.write(f"{field['id']} | {field['name']} | {field['type']}\n")
        
        print(f"Mapping file saved to: {mapping_file}")
        
        return jira_custom_fields
        
    except Exception as e:
        print(f"Error fetching custom fields: {e}")
        return None

def fetch_project_specific_fields():
    """Fetch project-specific field configuration"""
    
    config = JiraConfig()
    jira = JIRA(
        options=config.get_jira_options(),
        basic_auth=config.get_auth()
    )
    
    print(f"\nFetching project-specific fields for {config.project_key}...")
    
    try:
        # Get project
        project = jira.project(config.project_key)
        
        # Get issue types for the project
        issue_types = project.issueTypes
        
        print(f"Project: {project.name} ({project.key})")
        print(f"Issue Types: {len(issue_types)}")
        
        for issue_type in issue_types:
            print(f"  - {issue_type.name} (ID: {issue_type.id})")
        
        # Get create metadata for Task issue type
        try:
            create_meta = jira.createmeta(
                projectKeys=[config.project_key],
                issuetypeNames=['Task'],
                expand='projects.issuetypes.fields'
            )
            
            if create_meta and create_meta['projects']:
                project_meta = create_meta['projects'][0]
                issue_types_meta = project_meta['issuetypes']
                
                if issue_types_meta:
                    task_meta = issue_types_meta[0]  # Task issue type
                    fields = task_meta['fields']
                    
                    print(f"\nAvailable fields for Task issue type:")
                    print("=" * 60)
                    
                    available_fields = []
                    for field_id, field_info in fields.items():
                        if field_id.startswith('customfield_'):
                            field_data = {
                                'id': field_id,
                                'name': field_info.get('name', 'Unknown'),
                                'required': field_info.get('required', False),
                                'type': field_info.get('schema', {}).get('type', 'unknown'),
                                'allowedValues': field_info.get('allowedValues', [])
                            }
                            available_fields.append(field_data)
                    
                    # Sort by field ID
                    available_fields.sort(key=lambda x: x['id'])
                    
                    for field in available_fields:
                        print(f"ID: {field['id']}")
                        print(f"Name: {field['name']}")
                        print(f"Required: {field['required']}")
                        print(f"Type: {field['type']}")
                        if field['allowedValues']:
                            print(f"Allowed Values: {len(field['allowedValues'])} options")
                        print("-" * 30)
                    
                    # Save project-specific fields
                    project_fields_file = 'project_custom_fields.json'
                    with open(project_fields_file, 'w', encoding='utf-8') as f:
                        json.dump(available_fields, f, indent=2, ensure_ascii=False)
                    
                    print(f"\nProject-specific custom fields saved to: {project_fields_file}")
                    
        except Exception as e:
            print(f"Error fetching project metadata: {e}")
        
    except Exception as e:
        print(f"Error fetching project information: {e}")

def main():
    """Main function"""
    print("=== JIRA Custom Fields Fetcher ===\n")
    
    # Fetch all custom fields
    custom_fields = fetch_custom_fields()
    
    if custom_fields:
        # Fetch project-specific fields
        fetch_project_specific_fields()
        
        print("\n" + "=" * 80)
        print("SUMMARY:")
        print(f"Total custom fields found: {len(custom_fields)}")
        print("Files created:")
        print("  - jira_custom_fields.json (all custom fields)")
        print("  - custom_field_mapping.txt (mapping reference)")
        print("  - project_custom_fields.json (project-specific fields)")
        print("\nYou can now use these field IDs to map Freshdesk data to JIRA custom fields!")
    else:
        print("Failed to fetch custom fields")

if __name__ == "__main__":
    main()
