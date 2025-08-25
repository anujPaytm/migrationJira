"""
Mapper functions for transforming Freshdesk field values to JIRA format.
These functions are referenced in the field_mapping.json configuration.
"""

import re
from datetime import datetime
from typing import Any, List, Union, Optional


def map_priority(freshdesk_priority: int) -> str:
    """
    Map Freshdesk priority values to JIRA priority names.
    
    Args:
        freshdesk_priority: Freshdesk priority value (1-4)
        
    Returns:
        JIRA priority name
    """
    priority_mapping = {
        1: "Low",
        2: "Medium", 
        3: "High",
        4: "Urgent"
    }
    return priority_mapping.get(freshdesk_priority, "Medium")


def map_status(freshdesk_status: int) -> str:
    """
    Map Freshdesk status values to readable status names.
    
    Args:
        freshdesk_status: Freshdesk status value
        
    Returns:
        Human readable status name
    """
    status_mapping = {
        2: "Open",
        3: "Pending",
        4: "Resolved", 
        5: "Closed",
        6: "Waiting on Customer",
        7: "Waiting on Third Party"
    }
    return status_mapping.get(freshdesk_status, f"Status_{freshdesk_status}")


def map_source(freshdesk_source: int) -> str:
    """
    Map Freshdesk source values to readable source names.
    
    Args:
        freshdesk_source: Freshdesk source value
        
    Returns:
        Human readable source name
    """
    source_mapping = {
        1: "Email",
        2: "Portal", 
        3: "Phone",
        4: "Chat",
        5: "Feedback Widget",
        6: "Outbound Email",
        7: "E-commerce",
        8: "Bot",
        9: "Mobihelp",
        10: "Walkup",
        11: "Talkdesk",
        12: "Slack",
        13: "Teams",
        14: "WhatsApp",
        15: "SMS",
        16: "API"
    }
    return source_mapping.get(freshdesk_source, f"Source_{freshdesk_source}")


def map_user_from_id(user_id: int, user_data: dict = None) -> str:
    """
    Map user ID to user email from user_data.
    This function will be called with user_data context.
    
    Args:
        user_id: Freshdesk user ID
        user_data: User data dictionary containing agents and contacts
        
    Returns:
        User email or "Unknown" if not found
    """
    if not user_id or not user_data:
        return "Unknown"
    
    # Search in agents first
    agents = user_data.get('agents', {})
    if str(user_id) in agents:
        agent = agents[str(user_id)]
        # Agents have contact info nested in 'contact' object
        if 'contact' in agent and agent['contact'].get('email'):
            return agent['contact']['email']
    
    # Search in contacts
    contacts = user_data.get('contacts', {})
    if str(user_id) in contacts:
        contact = contacts[str(user_id)]
        # Contacts have email directly at the top level
        if contact.get('email'):
            return contact['email']
    
    return "Unknown"


def extract_emails(email_data: Union[str, List[str]]) -> str:
    """
    Extract email addresses from various email field formats.
    
    Args:
        email_data: Email data (string or list of strings)
        
    Returns:
        Comma-separated email addresses
    """
    if not email_data:
        return ""
    
    if isinstance(email_data, str):
        # Handle single email string
        return email_data.strip()
    
    if isinstance(email_data, list):
        emails = []
        for item in email_data:
            if isinstance(item, str):
                # Extract email from format like "'Name' <email@domain.com>"
                email_match = re.search(r'<([^>]+)>', item)
                if email_match:
                    emails.append(email_match.group(1))
                else:
                    # Assume it's a plain email
                    emails.append(item.strip())
        
        return ", ".join(emails)
    
    return str(email_data)


def format_date(date_string: str) -> str:
    """
    Format date string to JIRA compatible datetime format.
    
    Args:
        date_string: ISO format date string from Freshdesk
        
    Returns:
        Formatted datetime string for JIRA (YYYY-MM-DD HH:MM:SS)
    """
    if not date_string:
        return ""
    
    try:
        # Parse ISO format date
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        # Return in YYYY-MM-DD HH:MM:SS format for JIRA
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, AttributeError):
        return date_string


def join_list(list_data: List[Any]) -> str:
    """
    Join list items into a comma-separated string.
    
    Args:
        list_data: List of items to join
        
    Returns:
        Comma-separated string
    """
    if not list_data:
        return ""
    
    if isinstance(list_data, list):
        return ", ".join(str(item) for item in list_data)
    
    return str(list_data)


def truncate_text(text: str, max_length: int = 32000) -> str:
    """
    Truncate text to specified length to avoid JIRA field limits.
    
    Args:
        text: Text to truncate
        max_length: Maximum allowed length
        
    Returns:
        Truncated text
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."


def clean_html(html_text: str) -> str:
    """
    Remove HTML tags from text content.
    
    Args:
        html_text: HTML formatted text
        
    Returns:
        Clean text without HTML tags
    """
    if not html_text:
        return ""
    
    # Simple HTML tag removal
    clean_text = re.sub(r'<[^>]+>', '', html_text)
    # Remove extra whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text)
    return clean_text.strip()


def map_boolean(value: Any) -> str:
    """
    Map various boolean representations to string for Jira.
    
    Args:
        value: Value to convert to boolean string
        
    Returns:
        Boolean string value ("true" or "false")
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    
    if isinstance(value, str):
        return "true" if value.lower() in ('true', '1', 'yes', 'on') else "false"
    
    if isinstance(value, (int, float)):
        return "true" if bool(value) else "false"
    
    return "false"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in bytes to human readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string (e.g., "1.5 MB")
    """
    if not size_bytes:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    
    return f"{size_bytes:.1f} TB"

def extract_tags(tag_list: List[str]) -> str:
    """
    Extract tags from a list and return as comma-separated string.
    
    Args:
        tag_list: List of tags
        
    Returns:
        Comma-separated tag string
    """
    if not tag_list:
        return ""
    return ", ".join(tag_list)

def map_number(value: Any) -> str:
    """
    Map number values to string for Jira.
    
    Args:
        value: Number value from Freshdesk
        
    Returns:
        String value for Jira or empty string if invalid
    """
    if value is None:
        return ""
    try:
        return str(int(value))
    except (ValueError, TypeError):
        return ""

def map_custom_fields(custom_fields: dict) -> str:
    """
    Map custom fields to a string representation.
    
    Args:
        custom_fields: Dictionary of custom fields from Freshdesk
        
    Returns:
        String representation of custom fields
    """
    if not custom_fields:
        return ""
    
    # Convert custom fields to a readable string format
    formatted_fields = []
    for field_name, field_value in custom_fields.items():
        if field_value is not None and field_value != "":
            formatted_fields.append(f"{field_name}: {field_value}")
    
    return "; ".join(formatted_fields)

def map_id_to_string(value: Any) -> str:
    """
    Map ID values to string for Jira.
    
    Args:
        value: ID value from Freshdesk
        
    Returns:
        String value for Jira
    """
    if value is None:
        return ""
    return str(value)


def map_user_to_system_field(user_id: int, user_data: dict = None) -> dict:
    """
    Map user ID to system field format for assignee/reporter.
    Returns a dictionary with 'name' field for system fields.
    If user not found, returns None to use default (unassigned).
    
    Args:
        user_id: Freshdesk user ID
        user_data: User data dictionary containing agents and contacts
        
    Returns:
        Dictionary with 'name' field or None if user not found
    """
    if not user_id or not user_data:
        return None  # Will use default (unassigned)
    
    # Search in agents first
    agents = user_data.get('agents', {})
    if str(user_id) in agents:
        agent = agents[str(user_id)]
        # Agents have contact info nested in 'contact' object
        if 'contact' in agent and agent['contact'].get('email'):
            return {"name": agent['contact']['email']}
    
    # Search in contacts
    contacts = user_data.get('contacts', {})
    if str(user_id) in contacts:
        contact = contacts[str(user_id)]
        # Contacts have email directly at the top level
        if contact.get('email'):
            return {"name": contact['email']}
    
    return None  # Will use default (unassigned)


# Registry of all mapper functions for easy lookup
MAPPER_FUNCTIONS = {
    'map_priority': map_priority,
    'map_status': map_status,
    'map_source': map_source,
    'map_user_from_id': map_user_from_id,
    'map_user_to_system_field': map_user_to_system_field,
    'extract_emails': extract_emails,
    'extract_tags': extract_tags,
    'format_date': format_date,
    'join_list': join_list,
    'truncate_text': truncate_text,
    'clean_html': clean_html,
    'map_boolean': map_boolean,
    'map_number': map_number,
    'map_custom_fields': map_custom_fields,
    'map_id_to_string': map_id_to_string,
    'format_file_size': format_file_size
}


def get_mapper_function(function_name: str):
    """
    Get mapper function by name.
    
    Args:
        function_name: Name of the mapper function
        
    Returns:
        Mapper function or None if not found
    """
    return MAPPER_FUNCTIONS.get(function_name)


def apply_mapper_function(function_name: str, value: Any, context: dict = None) -> Any:
    """
    Apply mapper function to a value.
    
    Args:
        function_name: Name of the mapper function
        value: Value to transform
        context: Additional context (e.g., user_data for map_user_from_id)
        
    Returns:
        Transformed value
    """
    if not function_name:
        return value
    
    mapper_func = get_mapper_function(function_name)
    if mapper_func:
        try:
            if function_name == 'map_user_from_id' and context:
                return mapper_func(value, context)
            else:
                return mapper_func(value)
        except Exception as e:
            print(f"Warning: Error applying mapper function '{function_name}': {e}")
            return value
    
    return value
