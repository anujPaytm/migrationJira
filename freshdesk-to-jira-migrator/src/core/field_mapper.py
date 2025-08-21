"""
Field mapping logic for converting Freshdesk fields to JIRA fields.
Handles both mapped fields (sent to JIRA) and unmapped fields (added to description).
"""

import json
import os
import sys
from typing import Dict, Any, List, Optional, Tuple

# Add the project root to the path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from config.mapper_functions import apply_mapper_function


class FieldMapper:
    """
    Handles field mapping between Freshdesk and JIRA.
    """
    
    def __init__(self, mapping_file_path: str = "config/field_mapping.json"):
        """
        Initialize the field mapper with mapping configuration.
        
        Args:
            mapping_file_path: Path to the field mapping JSON file
        """
        self.mapping_file_path = mapping_file_path
        self.field_mapping = self._load_field_mapping()
    
    def _load_field_mapping(self) -> Dict[str, Any]:
        """
        Load field mapping from JSON file.
        
        Returns:
            Field mapping configuration
        """
        try:
            with open(self.mapping_file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Field mapping file not found at {self.mapping_file_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in field mapping file: {e}")
            return {}
    
    def get_field_mapping(self, field_name: str, field_category: str = "ticket_fields") -> Optional[Dict[str, Any]]:
        """
        Get mapping configuration for a specific field.
        
        Args:
            field_name: Name of the Freshdesk field
            field_category: Category of fields (ticket_fields, conversation_fields, etc.)
            
        Returns:
            Field mapping configuration or None if not found
        """
        category_mapping = self.field_mapping.get(field_category, {})
        return category_mapping.get(field_name)
    
    def is_field_mapped(self, field_name: str, field_category: str = "ticket_fields") -> bool:
        """
        Check if a field has a mapping configuration.
        
        Args:
            field_name: Name of the Freshdesk field
            field_category: Category of fields
            
        Returns:
            True if field is mapped, False otherwise
        """
        mapping = self.get_field_mapping(field_name, field_category)
        return mapping is not None and mapping.get("jira_field") is not None
    
    def map_field_value(self, field_name: str, field_value: Any, field_category: str = "ticket_fields", context: dict = None) -> Tuple[Optional[str], Optional[Any]]:
        """
        Map a field value according to its configuration.
        
        Args:
            field_name: Name of the Freshdesk field
            field_value: Value of the field
            field_category: Category of fields
            context: Additional context for mapper functions (e.g., user_data)
            
        Returns:
            Tuple of (jira_field_name, mapped_value) or (None, None) if not mapped
        """
        mapping = self.get_field_mapping(field_name, field_category)
        if not mapping:
            return None, None
        
        jira_field = mapping.get("jira_field")
        mapper_function = mapping.get("mapper_function")
        
        if not jira_field:
            return None, None
        
        # Apply mapper function if specified
        mapped_value = apply_mapper_function(mapper_function, field_value, context)
        
        return jira_field, mapped_value
    
    def get_unmapped_fields(self, data: Dict[str, Any], field_category: str = "ticket_fields") -> Dict[str, Any]:
        """
        Get fields that don't have mappings and should be added to description.
        
        Args:
            data: Freshdesk data dictionary
            field_category: Category of fields
            
        Returns:
            Dictionary of unmapped field names and values
        """
        unmapped_fields = {}
        
        for field_name, field_value in data.items():
            if not self.is_field_mapped(field_name, field_category):
                unmapped_fields[field_name] = field_value
        
        return unmapped_fields
    
    def format_unmapped_fields_for_description(self, unmapped_fields: Dict[str, Any], section_title: str = "Unmapped Fields") -> str:
        """
        Format unmapped fields for inclusion in JIRA description.
        
        Args:
            unmapped_fields: Dictionary of unmapped field names and values
            section_title: Title for the section
            
        Returns:
            Formatted string for description
        """
        if not unmapped_fields:
            return ""
        
        lines = [f"**{section_title}:**"]
        
        for field_name, field_value in unmapped_fields.items():
            if field_value is not None and field_value != "":
                # Handle different data types
                if isinstance(field_value, (list, dict)):
                    formatted_value = json.dumps(field_value, indent=2)
                else:
                    formatted_value = str(field_value)
                
                lines.append(f"**{field_name}:** {formatted_value}")
        
        return "\n".join(lines)
    
    def map_ticket_fields(self, ticket_data: Dict[str, Any], user_data: dict = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Map ticket fields to JIRA fields.
        
        Args:
            ticket_data: Freshdesk ticket data
            user_data: User data for context (for user mapping functions)
            
        Returns:
            Tuple of (mapped_fields, unmapped_fields)
        """
        mapped_fields = {}
        unmapped_fields = self.get_unmapped_fields(ticket_data, "ticket_fields")
        
        for field_name, field_value in ticket_data.items():
            jira_field, mapped_value = self.map_field_value(field_name, field_value, "ticket_fields", user_data)
            if jira_field and mapped_value is not None:
                mapped_fields[jira_field] = mapped_value
        
        return mapped_fields, unmapped_fields
    
    def map_conversation_fields(self, conversation_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Map conversation fields to JIRA fields.
        
        Args:
            conversation_data: Freshdesk conversation data
            
        Returns:
            Tuple of (mapped_fields, unmapped_fields)
        """
        mapped_fields = {}
        unmapped_fields = self.get_unmapped_fields(conversation_data, "conversation_fields")
        
        for field_name, field_value in conversation_data.items():
            jira_field, mapped_value = self.map_field_value(field_name, field_value, "conversation_fields")
            if jira_field and mapped_value is not None:
                mapped_fields[jira_field] = mapped_value
        
        return mapped_fields, unmapped_fields
    
    def map_attachment_fields(self, attachment_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Map attachment fields to JIRA fields.
        
        Args:
            attachment_data: Freshdesk attachment data
            
        Returns:
            Tuple of (mapped_fields, unmapped_fields)
        """
        mapped_fields = {}
        unmapped_fields = self.get_unmapped_fields(attachment_data, "attachment_fields")
        
        for field_name, field_value in attachment_data.items():
            jira_field, mapped_value = self.map_field_value(field_name, field_value, "attachment_fields")
            if jira_field and mapped_value is not None:
                mapped_fields[jira_field] = mapped_value
        
        return mapped_fields, unmapped_fields
    
    def map_user_fields(self, user_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Map user fields to JIRA fields.
        
        Args:
            user_data: Freshdesk user data
            
        Returns:
            Tuple of (mapped_fields, unmapped_fields)
        """
        mapped_fields = {}
        unmapped_fields = self.get_unmapped_fields(user_data, "user_fields")
        
        for field_name, field_value in user_data.items():
            jira_field, mapped_value = self.map_field_value(field_name, field_value, "user_fields")
            if jira_field and mapped_value is not None:
                mapped_fields[jira_field] = mapped_value
        
        return mapped_fields, unmapped_fields
    
    def get_all_mapped_fields(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all field mappings for reference.
        
        Returns:
            Dictionary of all field mappings
        """
        return self.field_mapping
    
    def reload_mapping(self):
        """
        Reload the field mapping from file.
        """
        self.field_mapping = self._load_field_mapping()
