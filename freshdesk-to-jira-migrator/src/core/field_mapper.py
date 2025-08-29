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
    Handles field mapping between Freshdesk and JIRA using configuration files.
    """
    
    def __init__(self, mapping_file_path: str = "config/field_mapping.json"):
        """
        Initialize the field mapper with mapping configuration.
        
        Args:
            mapping_file_path: Path to the field mapping JSON file
        """
        self.mapping_file_path = mapping_file_path
        self.field_mapping = self._load_field_mapping()
        self._overflow_tracker = 0  # Track which additional_info field to use next
        self._additional_info_fields = self._load_additional_info_fields()
    
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
    
    def _load_additional_info_fields(self) -> List[str]:
        """
        Load additional_info fields from the field mapping configuration.
        
        Returns:
            List of additional_info field IDs
        """
        try:
            # Get additional_info fields from conversation_fields configuration
            conversation_config = self.field_mapping.get("parent_fields", {}).get("conversation_fields", {})
            additional_fields = conversation_config.get("additional_overflow_fields", [])
            
            if not additional_fields:
                print("Warning: No additional_overflow_fields found in configuration")
                return []
            
            return additional_fields
        except Exception as e:
            print(f"Error loading additional_info fields: {e}")
            return []
    
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
    
    def map_field_value_with_system_field(self, field_name: str, field_value: Any, field_category: str = "ticket_fields", context: dict = None) -> Tuple[Optional[str], Optional[Any], Optional[str], Optional[Any]]:
        """
        Map a field value according to its configuration, including system field mapping.
        
        Args:
            field_name: Name of the Freshdesk field
            field_value: Value of the field
            field_category: Category of fields
            context: Additional context for mapper functions (e.g., user_data)
            
        Returns:
            Tuple of (jira_field_name, mapped_value, system_field_name, system_field_value) or (None, None, None, None) if not mapped
        """
        mapping = self.get_field_mapping(field_name, field_category)
        if not mapping:
            return None, None, None, None
        
        jira_field = mapping.get("jira_field")
        mapper_function = mapping.get("mapper_function")
        system_field = mapping.get("system_field")
        system_mapper_function = mapping.get("system_mapper_function")
        
        if not jira_field:
            return None, None, None, None
        
        # Apply mapper function if specified
        mapped_value = apply_mapper_function(mapper_function, field_value, context)
        
        # Apply system mapper function if specified
        system_field_value = None
        if system_field and system_mapper_function:
            system_field_value = apply_mapper_function(system_mapper_function, field_value, context)
        
        return jira_field, mapped_value, system_field, system_field_value
    
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
        
        # Always ensure we have a summary field
        summary = ticket_data.get('subject', '')
        if not summary or summary.strip() == '':
            ticket_id = ticket_data.get('id', 'Unknown')
            summary = f"Freshdesk Ticket #{ticket_id}: No Subject Provided"
        else:
            # Clean and truncate the summary if it's too long
            summary = summary.strip()
            if len(summary) > 255:  # JIRA summary limit
                summary = summary[:252] + "..."
        
        mapped_fields['summary'] = summary
        
        for field_name, field_value in ticket_data.items():
            # Check if this field has system field mapping
            jira_field, mapped_value, system_field, system_field_value = self.map_field_value_with_system_field(field_name, field_value, "ticket_fields", user_data)
            
            # Handle custom field mapping
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
            
            # Handle system field mapping
            if system_field and system_field_value is not None:
                mapped_fields[system_field] = system_field_value
        
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
                    # Handle overflow using generic method
                    overflow_mappings = self._handle_data_overflow(formatted_data, data_type, parent_mapping, jira_field)
                    mapped_fields.update(overflow_mappings)
                        
                elif data_type == "attachment_fields":
                    formatted_data = self._format_attachments_for_parent(data, user_data)
                    # Handle overflow using generic method
                    overflow_mappings = self._handle_data_overflow(formatted_data, data_type, parent_mapping, jira_field)
                    mapped_fields.update(overflow_mappings)
                else:
                    formatted_data = self._format_data_for_parent_field(data, data_type)
                    # Handle overflow for other field types if configured
                    if parent_mapping.get("overflow_fields") or parent_mapping.get("additional_overflow_fields"):
                        overflow_mappings = self._handle_data_overflow(formatted_data, data_type, parent_mapping, jira_field)
                        mapped_fields.update(overflow_mappings)
                    else:
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
        """Format conversations for parent field storage using pipe-separated format."""
        if not data:
            return ""
        
        # Ensure data is a list
        if not isinstance(data, list):
            print(f"Warning: Expected list for conversations, got {type(data)}")
            return ""
        
        headers = ["created_at", "updated_at", "conversation_id", "user_id", "private", "to_email", "from_email", "cc_email", "bcc_email"]
        lines = ["**— Conversations —**", '|'.join(headers)]
        
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
            
            # Use body_text if available, otherwise fall back to body
            body_text = conv.get('body_text', conv.get('body', ''))
            
            lines.extend([
                '|'.join(values),
                "",
                body_text,
                "---",
                ""
            ])
        
        return '\n'.join(lines)
    
    def _format_attachments_for_parent(self, data: List[Dict[str, Any]], user_data: dict = None) -> str:
        """Format attachments for parent field storage using pipe-separated format."""
        if not data:
            return ""
        
        # Ensure data is a list
        if not isinstance(data, list):
            print(f"Warning: Expected list for attachments, got {type(data)}")
            return ""
        
        headers = ["created_at", "updated_at", "attachment_id", "file name", "size", "user_id", "conversation_id"]
        lines = ["**— Attachment Details —**", '|'.join(headers)]
        
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
            
            lines.append('|'.join(values))
        
        return '\n'.join(lines)
    
    def _split_conversation_data(self, conversation_data: str, max_length: int, num_overflow_fields: int) -> List[str]:
        """
        Split conversation data into chunks that fit within the character limit.
        
        Args:
            conversation_data: Full conversation data string
            max_length: Maximum length per field
            num_overflow_fields: Number of overflow fields available
            
        Returns:
            List of conversation chunks
        """
        if len(conversation_data) <= max_length:
            return [conversation_data]
        
        chunks = []
        remaining_data = conversation_data
        total_fields = 1 + num_overflow_fields  # Original field + overflow fields
        
        for i in range(total_fields):
            if not remaining_data:
                break
                
            if i == 0:
                # First chunk - include header
                if len(remaining_data) <= max_length:
                    chunks.append(remaining_data)
                    break
                else:
                    # Find a good break point (end of a conversation)
                    break_point = self._find_conversation_break_point(remaining_data, max_length)
                    chunks.append(remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
            else:
                # Overflow chunks - add continuation header
                continuation_header = f"**— Conversation Details (Continued {i}) —**\n"
                available_length = max_length - len(continuation_header)
                
                if len(remaining_data) <= available_length:
                    chunks.append(continuation_header + remaining_data)
                    break
                else:
                    # Find a good break point
                    break_point = self._find_conversation_break_point(remaining_data, available_length)
                    chunks.append(continuation_header + remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
        
        return chunks
    
    def _find_conversation_break_point(self, data: str, max_length: int) -> int:
        """
        Find a good break point in conversation data that doesn't cut in the middle of a conversation.
        
        Args:
            data: Conversation data string
            max_length: Maximum length for this chunk
            
        Returns:
            Index to break at
        """
        if len(data) <= max_length:
            return len(data)
        
        # Look for conversation separators
        separators = ["---", "\n\n---\n\n"]
        
        for separator in separators:
            # Find the last occurrence of the separator before max_length
            last_separator_pos = data.rfind(separator, 0, max_length)
            if last_separator_pos > 0:
                return last_separator_pos + len(separator)
        
        # If no good separator found, break at max_length but try to break at a newline
        break_point = data.rfind('\n', 0, max_length)
        if break_point > max_length * 0.8:  # Only use newline if it's not too far from max_length
            return break_point + 1
        
        return max_length
    
    def _split_attachment_data(self, attachment_data: str, max_length: int, num_overflow_fields: int) -> List[str]:
        """
        Split attachment data into chunks that fit within the character limit.
        
        Args:
            attachment_data: Full attachment data string
            max_length: Maximum length per field
            num_overflow_fields: Number of overflow fields available
            
        Returns:
            List of attachment chunks
        """
        if len(attachment_data) <= max_length:
            return [attachment_data]
        
        chunks = []
        remaining_data = attachment_data
        total_fields = 1 + num_overflow_fields  # Original field + overflow fields
        
        for i in range(total_fields):
            if not remaining_data:
                break
                
            if i == 0:
                # First chunk - include header
                if len(remaining_data) <= max_length:
                    chunks.append(remaining_data)
                    break
                else:
                    # Find a good break point (end of an attachment)
                    break_point = self._find_attachment_break_point(remaining_data, max_length)
                    chunks.append(remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
            else:
                # Overflow chunks - add continuation header
                continuation_header = f"**— Attachment Details (Continued {i}) —**\n"
                available_length = max_length - len(continuation_header)
                
                if len(remaining_data) <= available_length:
                    chunks.append(continuation_header + remaining_data)
                    break
                else:
                    # Find a good break point
                    break_point = self._find_attachment_break_point(remaining_data, available_length)
                    chunks.append(continuation_header + remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
        
        return chunks
    
    def _find_attachment_break_point(self, data: str, max_length: int) -> int:
        """
        Find a good break point in attachment data that doesn't cut in the middle of an attachment.
        
        Args:
            data: Attachment data string
            max_length: Maximum length for this chunk
            
        Returns:
            Index to break at
        """
        if len(data) <= max_length:
            return len(data)
        
        # Look for attachment separators (newlines between attachments)
        # Find the last occurrence of double newline before max_length
        last_separator_pos = data.rfind('\n\n', 0, max_length)
        if last_separator_pos > 0:
            return last_separator_pos + 2
        
        # If no good separator found, break at max_length but try to break at a newline
        break_point = data.rfind('\n', 0, max_length)
        if break_point > max_length * 0.8:  # Only use newline if it's not too far from max_length
            return break_point + 1
        
        return max_length
    
    def _handle_data_overflow(self, data: str, data_type: str, parent_mapping: dict, jira_field: str) -> Dict[str, str]:
        """
        Generic method to handle data overflow for any field type with sequential overflow logic.
        
        Args:
            data: Formatted data string
            data_type: Type of data (conversation_fields, attachment_fields, etc.)
            parent_mapping: Parent field mapping configuration
            jira_field: Main Jira field name
            
        Returns:
            Dictionary of field mappings
        """
        mapped_fields = {}
        overflow_fields = parent_mapping.get("overflow_fields", [])
        additional_overflow_fields = parent_mapping.get("additional_overflow_fields", [])
        max_length = parent_mapping.get("max_length", 32000)
        
        if len(data) <= max_length:
            mapped_fields[jira_field] = data
            return mapped_fields
        
        # Sequential overflow logic:
        # 1. Use reserved overflow fields first (if any)
        # 2. Then use additional_info fields sequentially
        
        if data_type == "conversation_fields":
            return self._handle_conversation_overflow(data, overflow_fields, max_length, jira_field)
        elif data_type == "attachment_fields":
            return self._handle_attachment_overflow(data, overflow_fields, max_length, jira_field)
        else:
            # Generic overflow for other types
            all_overflow_fields = overflow_fields + additional_overflow_fields
            if not all_overflow_fields:
                mapped_fields[jira_field] = data
                return mapped_fields
            
            # Split data based on type
            if data_type == "conversation_fields":
                chunks = self._split_conversation_data(data, max_length, len(all_overflow_fields))
            else:
                # Generic splitting for other data types
                chunks = self._split_generic_data(data, max_length, len(all_overflow_fields), data_type)
            
            # Assign chunks to fields
            mapped_fields[jira_field] = chunks[0] if chunks else ""
            
            for i, overflow_field in enumerate(all_overflow_fields):
                if i + 1 < len(chunks):
                    mapped_fields[overflow_field] = chunks[i + 1]
            
            return mapped_fields
    
    def _handle_conversation_overflow(self, data: str, overflow_fields: List[str], max_length: int, jira_field: str) -> Dict[str, str]:
        """
        Handle conversation overflow with dedicated overflow field and smart additional field usage.
        
        Args:
            data: Formatted conversation data string
            overflow_fields: Dedicated overflow fields for conversations (FD_conversation2, FD_conversation3)
            max_length: Maximum length per field
            jira_field: Main Jira field name
            
        Returns:
            Dictionary of field mappings
        """
        mapped_fields = {}
        
        # First, try to fit data in main field and dedicated overflow fields
        dedicated_overflow_fields = overflow_fields  # FD_conversation2, FD_conversation3
        
        # Calculate total fields needed
        total_dedicated_fields = 1 + len(dedicated_overflow_fields)  # main + dedicated overflow
        
        # Split data for dedicated fields first
        chunks = self._split_conversation_data(data, max_length, len(dedicated_overflow_fields))
        
        # Assign to main field and dedicated overflow fields
        mapped_fields[jira_field] = chunks[0] if chunks else ""
        
        for i, overflow_field in enumerate(dedicated_overflow_fields):
            if i + 1 < len(chunks):
                mapped_fields[overflow_field] = chunks[i + 1]
        
        # If we still have data to overflow, use additional fields sequentially
        if len(chunks) > total_dedicated_fields:
            remaining_chunks = chunks[total_dedicated_fields:]
            
            for chunk in remaining_chunks:
                next_field = self._get_next_additional_info_field()
                if next_field:
                    mapped_fields[next_field] = chunk
                else:
                    # No more additional_info fields available
                    break
        
        return mapped_fields
    
    def _handle_attachment_overflow(self, data: str, overflow_fields: List[str], max_length: int, jira_field: str) -> Dict[str, str]:
        """
        Handle attachment overflow with dedicated overflow field and smart additional field usage.
        
        Args:
            data: Formatted attachment data string
            overflow_fields: Dedicated overflow fields for attachments (FD_attachment_details2)
            max_length: Maximum length per field
            jira_field: Main Jira field name
            
        Returns:
            Dictionary of field mappings
        """
        mapped_fields = {}
        
        # First, try to fit data in main field and dedicated overflow fields
        dedicated_overflow_fields = overflow_fields  # FD_attachment_details2
        
        # Calculate total fields needed
        total_dedicated_fields = 1 + len(dedicated_overflow_fields)  # main + dedicated overflow
        
        # Split data for dedicated fields first
        chunks = self._split_attachment_data(data, max_length, len(dedicated_overflow_fields))
        
        # Assign to main field and dedicated overflow fields
        mapped_fields[jira_field] = chunks[0] if chunks else ""
        
        for i, overflow_field in enumerate(dedicated_overflow_fields):
            if i + 1 < len(chunks):
                mapped_fields[overflow_field] = chunks[i + 1]
        
        # If we still have data to overflow, use additional fields sequentially
        if len(chunks) > total_dedicated_fields:
            remaining_chunks = chunks[total_dedicated_fields:]
            
            for chunk in remaining_chunks:
                next_field = self._get_next_additional_info_field()
                if next_field:
                    mapped_fields[next_field] = chunk
                else:
                    # No more additional_info fields available
                    break
        
        return mapped_fields
    
    def _split_generic_data(self, data: str, max_length: int, num_overflow_fields: int, data_type: str) -> List[str]:
        """
        Generic method to split any type of data into chunks.
        
        Args:
            data: Data string to split
            max_length: Maximum length per field
            num_overflow_fields: Number of overflow fields available
            data_type: Type of data for header formatting
            
        Returns:
            List of data chunks
        """
        if len(data) <= max_length:
            return [data]
        
        chunks = []
        remaining_data = data
        total_fields = 1 + num_overflow_fields
        
        for i in range(total_fields):
            if not remaining_data:
                break
                
            if i == 0:
                # First chunk - include header
                if len(remaining_data) <= max_length:
                    chunks.append(remaining_data)
                    break
                else:
                    # Find a good break point
                    break_point = self._find_generic_break_point(remaining_data, max_length)
                    chunks.append(remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
            else:
                # Overflow chunks - add continuation header
                data_type_name = data_type.replace('_', ' ').title()
                continuation_header = f"**— {data_type_name} (Continued {i}) —**\n"
                available_length = max_length - len(continuation_header)
                
                if len(remaining_data) <= available_length:
                    chunks.append(continuation_header + remaining_data)
                    break
                else:
                    # Find a good break point
                    break_point = self._find_generic_break_point(remaining_data, available_length)
                    chunks.append(continuation_header + remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
        
        return chunks
    
    def _find_generic_break_point(self, data: str, max_length: int) -> int:
        """
        Find a good break point in generic data.
        
        Args:
            data: Data string
            max_length: Maximum length for this chunk
            
        Returns:
            Index to break at
        """
        if len(data) <= max_length:
            return len(data)
        
        # Look for common separators
        separators = ["\n\n", "\n", " ", ""]
        
        for separator in separators:
            if separator:
                last_separator_pos = data.rfind(separator, 0, max_length)
                if last_separator_pos > 0:
                    return last_separator_pos + len(separator)
            else:
                # If no separator found, break at max_length
                return max_length
        
        return max_length
    
    def _get_next_additional_info_field(self) -> Optional[str]:
        """
        Get the next available additional_info field for overflow data.
        
        Returns:
            Next available additional_info field ID or None if all are used
        """
        if self._overflow_tracker >= len(self._additional_info_fields):
            return None
        
        field_id = self._additional_info_fields[self._overflow_tracker]
        self._overflow_tracker += 1
        return field_id
    
    def handle_description_overflow(self, description: str, max_length: int = 32000) -> Dict[str, str]:
        """
        Handle description overflow using additional_info fields from configuration.
        
        Args:
            description: The complete description text
            max_length: Maximum length per field
            
        Returns:
            Dictionary mapping field names to description chunks
        """
        overflow_mappings = {}
        
        if len(description) <= max_length:
            overflow_mappings["description"] = description
            return overflow_mappings
        
        # Split description into chunks
        chunks = self._split_description_data(description, max_length, len(self._additional_info_fields))
        
        # Assign chunks to fields
        overflow_mappings["description"] = chunks[0] if chunks else ""
        
        # Use additional_info fields from configuration
        chunk_index = 1
        for field_id in self._additional_info_fields:
            if chunk_index < len(chunks):
                overflow_mappings[field_id] = chunks[chunk_index]
                chunk_index += 1
            else:
                break
        
        return overflow_mappings
    
    def _split_description_data(self, data: str, max_length: int, num_overflow_fields: int) -> List[str]:
        """
        Split description data into chunks for overflow fields.
        
        Args:
            data: Description data string
            max_length: Maximum length per field
            num_overflow_fields: Number of overflow fields available
            
        Returns:
            List of description chunks
        """
        if len(data) <= max_length:
            return [data]
        
        chunks = []
        remaining_data = data
        total_fields = 1 + num_overflow_fields  # Original field + overflow fields
        
        for i in range(total_fields):
            if not remaining_data:
                break
                
            if i == 0:
                # First chunk - include header
                if len(remaining_data) <= max_length:
                    chunks.append(remaining_data)
                    break
                else:
                    # Find a good break point (end of a section)
                    break_point = self._find_description_break_point(remaining_data, max_length)
                    chunks.append(remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
            else:
                # Overflow chunks - add continuation header
                continuation_header = f"**— Description (Continued {i}) —**\n"
                available_length = max_length - len(continuation_header)
                
                if len(remaining_data) <= available_length:
                    chunks.append(continuation_header + remaining_data)
                    break
                else:
                    # Find a good break point
                    break_point = self._find_description_break_point(remaining_data, available_length)
                    chunks.append(continuation_header + remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
        
        return chunks
    
    def _find_description_break_point(self, data: str, max_length: int) -> int:
        """
        Find a good break point in description data that doesn't cut in the middle of a section.
        
        Args:
            data: Description data string
            max_length: Maximum length for this chunk
            
        Returns:
            Index to break at
        """
        if len(data) <= max_length:
            return len(data)
        
        # Look for section breaks first
        section_breaks = ["\n\n**—", "\n**—", "\n\n##", "\n##", "\n\n###", "\n###"]
        
        for break_pattern in section_breaks:
            last_break_pos = data.rfind(break_pattern, 0, max_length)
            if last_break_pos > 0:
                return last_break_pos
        
        # Look for paragraph breaks
        paragraph_breaks = ["\n\n", "\n"]
        
        for break_pattern in paragraph_breaks:
            last_break_pos = data.rfind(break_pattern, 0, max_length)
            if last_break_pos > 0:
                return last_break_pos + len(break_pattern)
        
        # If no good break point found, break at max_length
        return max_length
