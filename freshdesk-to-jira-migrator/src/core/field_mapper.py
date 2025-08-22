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
from config.mapper_functions import apply_mapper_function, clean_html


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
    
    def is_parent_field_mapped(self, parent_field_name: str) -> bool:
        """
        Check if a parent field has a mapping to a JIRA field.
        
        Args:
            parent_field_name: Name of the parent field (ticket_metadata, conversations, attachments)
            
        Returns:
            True if the parent field is mapped, False otherwise
        """
        mapping = self.get_field_mapping(parent_field_name, "parent_fields")
        return mapping is not None and mapping.get("jira_field") is not None
    
    def get_parent_field_mapping(self, parent_field_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the mapping for a parent field.
        
        Args:
            parent_field_name: Name of the parent field
            
        Returns:
            Mapping dictionary or None if not found
        """
        return self.get_field_mapping(parent_field_name, "parent_fields")
    
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
            elif jira_field and mapped_value is False:  # Allow False boolean values
                mapped_fields[jira_field] = mapped_value
            elif jira_field and mapped_value == 0:  # Allow zero numeric values
                mapped_fields[jira_field] = mapped_value
            elif jira_field and mapped_value == "":  # Allow empty string values
                mapped_fields[jira_field] = mapped_value
            elif jira_field and mapped_value == "false":  # Allow "false" string values
                mapped_fields[jira_field] = mapped_value
            elif jira_field and mapped_value == "0":  # Allow "0" string values
                mapped_fields[jira_field] = mapped_value
            elif jira_field and isinstance(mapped_value, str):  # Allow any string values
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
    
    def map_hierarchical_fields(self, data: Any, data_type: str, user_data: dict = None) -> Tuple[Dict[str, Any], Any]:
        """
        Map fields using hierarchical approach: check parent field first, then individual fields.
        
        Args:
            data: Data to map (ticket_data, conversations, attachments)
            data_type: Type of data ('ticket_fields', 'conversation_fields', 'attachment_fields', 'user_fields')
            user_data: User data for context
            
        Returns:
            Tuple of (mapped_fields, unmapped_fields)
        """
        mapped_fields = {}
        unmapped_fields = {}
        
        # First check if parent field is mapped
        if self.is_parent_field_mapped(data_type):
            # Parent field exists - map all data to parent field
            parent_mapping = self.get_parent_field_mapping(data_type)
            jira_field = parent_mapping.get("jira_field")
            
            if jira_field:
                # Format all data as a single field value using colon-separated format
                if data_type == "conversation_fields":
                    formatted_data = self._format_conversations_for_parent(data, user_data)
                elif data_type == "attachment_fields":
                    formatted_data = self._format_attachments_for_parent(data, user_data)
                else:
                    formatted_data = self._format_data_for_parent_field(data, data_type)
                mapped_fields[jira_field] = formatted_data
                return mapped_fields, unmapped_fields
        else:
            # Parent field doesn't exist - check individual fields
            field_category = data_type  # Use the exact category name
            
            # Handle different data types
            if isinstance(data, dict):
                for field_name, field_value in data.items():
                    # Skip HTML fields - use their text counterparts
                    if field_name in ['description', 'body', 'structured_description']:
                        continue
                    
                    jira_field, mapped_value = self.map_field_value(field_name, field_value, field_category, user_data)
                    if jira_field and mapped_value is not None:
                        mapped_fields[jira_field] = mapped_value
                    else:
                        unmapped_fields[field_name] = field_value
            elif isinstance(data, list):
                # For lists (like conversations, attachments), filter out HTML fields
                filtered_data = []
                for item in data:
                    if isinstance(item, dict):
                        # Create a copy without HTML fields
                        filtered_item = {}
                        for key, value in item.items():
                            if key not in ['body', 'description', 'structured_description']:
                                filtered_item[key] = value
                        filtered_data.append(filtered_item)
                    else:
                        filtered_data.append(item)
                unmapped_fields = filtered_data
            else:
                unmapped_fields = data
        
        return mapped_fields, unmapped_fields
    
    def _format_data_for_parent_field(self, data: Dict[str, Any], data_type: str) -> str:
        """
        Format data for storage in a parent field.
        
        Args:
            data: Data to format
            data_type: Type of data
            
        Returns:
            Formatted string
        """
        if data_type == "ticket_metadata":
            return self._format_ticket_metadata_for_parent(data)
        elif data_type == "conversations":
            return self._format_conversations_for_parent(data)
        elif data_type == "attachments":
            return self._format_attachments_for_parent(data)
        else:
            return json.dumps(data, indent=2)
    
    def _format_ticket_metadata_for_parent(self, data: Dict[str, Any]) -> str:
        """Format ticket metadata for parent field storage."""
        lines = ["**— Freshdesk Ticket Metadata —**"]
        
        for field_name, field_value in data.items():
            # Skip HTML fields - only use their text counterparts
            if field_name in ['description', 'body', 'structured_description']:
                continue
                
            if field_value is not None and field_value != "":
                if isinstance(field_value, list):
                    field_value = ', '.join(str(v) for v in field_value)
                lines.append(f"{field_name}: {field_value}")
        
        return '\n'.join(lines)
    
    def _format_conversations_for_parent(self, data: List[Dict[str, Any]], user_data: dict = None) -> str:
        """Format conversations for parent field storage using colon-separated format."""
        if not data:
            return ""
        
        headers = ["created_at", "updated_at", "conversation_id", "user_id", "private", "to_email", "from_email", "cc_email", "bcc_email"]
        lines = ["**— Conversations —**", ':'.join(headers)]
        
        for conv in data:
            # Get user information from user_data
            user_email = 'NA'
            if user_data and conv.get('user_id'):
                user_id = str(conv.get('user_id'))
                # Search in agents first
                agents = user_data.get('agents', {})
                if user_id in agents:
                    agent = agents[user_id]
                    if 'contact' in agent and agent['contact'].get('email'):
                        user_email = agent['contact']['email']
                else:
                    # Search in contacts
                    contacts = user_data.get('contacts', {})
                    if user_id in contacts:
                        contact = contacts[user_id]
                        if contact.get('email'):
                            user_email = contact['email']
            
            # Format privacy status
            is_private = conv.get('private', False)
            privacy_status = "private" if is_private else "public"
            
            # Get email fields
            to_emails = ', '.join(conv.get('to_emails', []))
            from_email = conv.get('from_email', 'N/A')
            cc_emails = ', '.join(conv.get('cc_emails', []))
            bcc_emails = ', '.join(conv.get('bcc_emails', []))
            
            values = [
                str(conv.get('created_at', 'N/A')),
                str(conv.get('updated_at', 'N/A')),
                str(conv.get('id', 'N/A')),
                str(user_email),
                str(privacy_status),
                str(to_emails),
                str(from_email),
                str(cc_emails),
                str(bcc_emails)
            ]
            
            # Only use body_text, never body (HTML)
            body_text = conv.get('body_text', '')
            
            lines.extend([
                ':'.join(values),
                "",
                body_text,
                "---",
                ""
            ])
        
        return '\n'.join(lines)
    
    def _format_attachments_for_parent(self, data: List[Dict[str, Any]], user_data: dict = None) -> str:
        """Format attachments for parent field storage using colon-separated format."""
        if not data:
            return ""
        
        headers = ["created_at", "updated_at", "attachment_id", "newNamed file name", "size", "user_id", "conversation_id"]
        lines = ["**— Attachment Details —**", ':'.join(headers)]
        
        for attachment in data:
            # Get user information from user_data
            user_email = 'NA'
            if user_data and attachment.get('user_id'):
                user_id = str(attachment.get('user_id'))
                # Search in agents first
                agents = user_data.get('agents', {})
                if user_id in agents:
                    agent = agents[user_id]
                    if 'contact' in agent and agent['contact'].get('email'):
                        user_email = agent['contact']['email']
                else:
                    # Search in contacts
                    contacts = user_data.get('contacts', {})
                    if user_id in contacts:
                        contact = contacts[user_id]
                        if contact.get('email'):
                            user_email = contact['email']
            
            attachment_id = attachment.get('id', 'N/A')
            original_name = attachment.get('name', 'N/A')
            new_name = f"{attachment_id}_{original_name}"
            
            values = [
                str(attachment.get('created_at', 'N/A')),
                str(attachment.get('updated_at', 'N/A')),
                str(attachment_id),
                str(new_name),
                str(attachment.get('size', 'N/A')),
                str(user_email),
                str(attachment.get('conversation_id', 'N/A'))
            ]
            
            lines.append(':'.join(values))
        
        return '\n'.join(lines)
