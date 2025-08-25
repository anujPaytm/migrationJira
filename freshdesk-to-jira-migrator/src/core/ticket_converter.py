"""
Ticket conversion logic for transforming Freshdesk tickets to JIRA issues.
Handles field mapping, description formatting, and custom field assignment.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from .field_mapper import FieldMapper
from config.mapper_functions import truncate_text, clean_html


class TicketConverter:
    """
    Converts Freshdesk tickets to JIRA issues with proper field mapping.
    """
    
    def __init__(self, field_mapper: FieldMapper):
        """
        Initialize the ticket converter.
        
        Args:
            field_mapper: Field mapper instance
        """
        self.field_mapper = field_mapper
    
    def convert_to_jira_issue(self, 
                             ticket: Dict[str, Any],
                             conversations: List[Dict[str, Any]] = None,
                             ticket_attachments: List[Dict[str, Any]] = None,
                             conversation_attachments: List[Dict[str, Any]] = None,
                             user_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Convert a Freshdesk ticket to JIRA issue format.
        
        Args:
            ticket: Freshdesk ticket data
            conversations: List of conversation data
            ticket_attachments: List of ticket attachment data
            conversation_attachments: List of conversation attachment data
            user_data: User information data
            
        Returns:
            JIRA issue dictionary
        """
        # Initialize JIRA issue structure
        jira_issue = {
            "fields": {
                "project": {"key": "FTJM"},  # Default project key
                "issuetype": {"name": "Task"}  # Default issue type
            }
        }
        
        # Map ticket fields using regular approach (not hierarchical for ticket fields)
        mapped_fields, unmapped_ticket_fields = self.field_mapper.map_ticket_fields(ticket, user_data)
        
        # Add mapped fields to JIRA issue
        for field_name, field_value in mapped_fields.items():
            jira_issue["fields"][field_name] = field_value
        
        # Ensure summary field is always set
        if not jira_issue["fields"].get('summary') or jira_issue["fields"]['summary'].strip() == '':
            ticket_id = ticket.get('id', 'Unknown')
            jira_issue["fields"]['summary'] = f"Freshdesk Ticket #{ticket_id}: No Subject Provided"
        
        # Build description using hierarchical approach
        description_parts = []
        
        # Add original description if available (use description_text if available, otherwise fall back to description)
        description_text = ticket.get('description_text', ticket.get('description', ''))
        if description_text:
            description_parts.append(f"**— Description —**\n{description_text}")
        
        # Add unmapped ticket fields to description (only if not mapped to custom fields)
        # Exclude HTML fields and description_text to avoid duplication
        if unmapped_ticket_fields:
            metadata_lines = ["**— Freshdesk Ticket Metadata —**"]
            for field_name, field_value in unmapped_ticket_fields.items():
                # Skip HTML description fields and description_text to avoid duplication
                if field_name in ['description', 'structured_description', 'description_text']:
                    continue
                    
                if field_value is not None and field_value != "":
                    if isinstance(field_value, list):
                        field_value = ', '.join(str(v) for v in field_value)
                    metadata_lines.append(f"{field_name}: {field_value}")
            
            # Only add metadata section if there are actual fields to show
            if len(metadata_lines) > 1:
                description_parts.append('\n'.join(metadata_lines))
        
        # Map conversations using hierarchical approach
        if conversations:
            conv_mapped_fields, conv_unmapped_fields = self.field_mapper.map_hierarchical_fields(conversations, "conversation_fields", user_data)
            
            # Handle conversation overflow properly
            for field_name, field_value in conv_mapped_fields.items():
                if len(str(field_value)) > 32000:
                    # Handle conversation overflow
                    overflow_mappings = self._handle_conversation_overflow(field_value, field_name)
                    for overflow_field, overflow_value in overflow_mappings.items():
                        jira_issue["fields"][overflow_field] = overflow_value
                else:
                    jira_issue["fields"][field_name] = field_value
            
            # Add unmapped conversations to description (only if parent field is not mapped)
            if conv_unmapped_fields and not conv_mapped_fields:
                formatted_conversations = self._format_conversations_colon_separated(conversations, user_data)
                if formatted_conversations:
                    description_parts.append(formatted_conversations)
        
        # Map attachments using hierarchical approach
        all_attachments = ticket_attachments + conversation_attachments if ticket_attachments and conversation_attachments else (ticket_attachments or conversation_attachments or [])
        
        if all_attachments:
            att_mapped_fields, att_unmapped_fields = self.field_mapper.map_hierarchical_fields(all_attachments, "attachment_fields", user_data)
            
            # Handle attachment overflow properly
            for field_name, field_value in att_mapped_fields.items():
                if len(str(field_value)) > 32000:
                    # Handle attachment overflow
                    overflow_mappings = self._handle_attachment_overflow(field_value, field_name)
                    for overflow_field, overflow_value in overflow_mappings.items():
                        jira_issue["fields"][overflow_field] = overflow_value
                else:
                    jira_issue["fields"][field_name] = field_value
            
            # Add unmapped attachments to description (only if parent field is not mapped)
            if att_unmapped_fields and not att_mapped_fields:
                formatted_attachments = self._format_attachments_colon_separated(all_attachments, user_data)
                if formatted_attachments:
                    description_parts.append(formatted_attachments)
        
        # Combine all description parts with overflow handling
        if description_parts:
            # Check total length before joining to avoid expensive operations
            total_length = sum(len(part) for part in description_parts) + (len(description_parts) - 1) * 2  # Account for '\n\n' separators
            max_description_length = 32000  # Leave some buffer
            
            if total_length > max_description_length:
                print(f"Warning: Description too long ({total_length} chars), using overflow fields")
                
                # Use overflow fields instead of truncating
                full_description = '\n\n'.join(description_parts)
                overflow_mappings = self._handle_description_overflow(full_description, max_description_length)
                
                # Add overflow fields to the JIRA issue
                for field_name, field_value in overflow_mappings.items():
                    jira_issue["fields"][field_name] = field_value
                
                # Set the main description to the first chunk
                jira_issue["fields"]["description"] = overflow_mappings.get("description", "")
            else:
                full_description = '\n\n'.join(description_parts)
                jira_issue["fields"]["description"] = full_description
        
        # Don't add user information to avoid description length issues
        # User mapping is already handled in the field mapping above
        
        return jira_issue
    
    def _format_description_section(self, title: str, content: str) -> str:
        """
        Format a description section with title and content.
        
        Args:
            title: Section title
            content: Section content
            
        Returns:
            Formatted section text
        """
        if not content:
            return ""
        
        # Clean HTML if present
        clean_content = clean_html(content)
        
        return f"**{title}:**\n{clean_content}"
    
    def _format_conversations(self, conversations: List[Dict[str, Any]]) -> str:
        """
        Format conversations for description.
        
        Args:
            conversations: List of conversation data
            
        Returns:
            Formatted conversations text
        """
        if not conversations:
            return ""
        
        lines = ["**Conversations:**"]
        
        for i, conversation in enumerate(conversations, 1):
            lines.append(f"\n**Conversation {i}:**")
            
            # Map conversation fields
            mapped_fields, unmapped_fields = self.field_mapper.map_conversation_fields(conversation)
            
            # Add mapped fields
            for field_name, field_value in mapped_fields.items():
                if field_value is not None and field_value != "":
                    lines.append(f"**{field_name}:** {field_value}")
            
            # Add unmapped fields
            for field_name, field_value in unmapped_fields.items():
                if field_value is not None and field_value != "":
                    if isinstance(field_value, (list, dict)):
                        formatted_value = json.dumps(field_value, indent=2)
                    else:
                        formatted_value = str(field_value)
                    lines.append(f"**{field_name}:** {formatted_value}")
        
        return "\n".join(lines)
    
    def _format_attachments(self, attachments: List[Dict[str, Any]], title: str) -> str:
        """
        Format attachments for description.
        
        Args:
            attachments: List of attachment data
            title: Section title
            
        Returns:
            Formatted attachments text
        """
        if not attachments:
            return ""
        
        lines = [f"**{title}:**"]
        
        for i, attachment in enumerate(attachments, 1):
            lines.append(f"\n**Attachment {i}:**")
            
            # Map attachment fields
            mapped_fields, unmapped_fields = self.field_mapper.map_attachment_fields(attachment)
            
            # Add mapped fields
            for field_name, field_value in mapped_fields.items():
                if field_value is not None and field_value != "":
                    lines.append(f"**{field_name}:** {field_value}")
            
            # Add unmapped fields
            for field_name, field_value in unmapped_fields.items():
                if field_value is not None and field_value != "":
                    if isinstance(field_value, (list, dict)):
                        formatted_value = json.dumps(field_value, indent=2)
                    else:
                        formatted_value = str(field_value)
                    lines.append(f"**{field_name}:** {formatted_value}")
        
        return "\n".join(lines)
    
    def set_project_key(self, jira_issue: Dict[str, Any], project_key: str):
        """
        Set the project key for a JIRA issue.
        
        Args:
            jira_issue: JIRA issue dictionary
            project_key: Project key
        """
        jira_issue["fields"]["project"]["key"] = project_key
    
    def set_issue_type(self, jira_issue: Dict[str, Any], issue_type: str):
        """
        Set the issue type for a JIRA issue.
        
        Args:
            jira_issue: JIRA issue dictionary
            issue_type: Issue type name
        """
        jira_issue["fields"]["issuetype"]["name"] = issue_type
    
    def add_custom_field(self, jira_issue: Dict[str, Any], field_name: str, field_value: Any):
        """
        Add a custom field to the JIRA issue.
        
        Args:
            jira_issue: JIRA issue dictionary
            field_name: Custom field name
            field_value: Field value
        """
        jira_issue["fields"][field_name] = field_value
    
    def get_mapped_fields_summary(self, ticket: Dict[str, Any], user_data: dict = None) -> Dict[str, Any]:
        """
        Get a summary of mapped and unmapped fields for a ticket.
        
        Args:
            ticket: Freshdesk ticket data
            user_data: User data for context
            
        Returns:
            Summary dictionary
        """
        mapped_fields, unmapped_fields = self.field_mapper.map_ticket_fields(ticket, user_data)
        
        return {
            "mapped_fields": list(mapped_fields.keys()),
            "unmapped_fields": list(unmapped_fields.keys()),
            "total_fields": len(ticket),
            "mapping_coverage": len(mapped_fields) / len(ticket) if ticket else 0
        }
    
    def _format_conversations_colon_separated(self, conversations: List[Dict[str, Any]], user_data: dict = None) -> str:
        """
        Format conversations in pipe-separated format (regardless of where they're stored).
        
        Args:
            conversations: List of conversation data
            user_data: User data for context
            
        Returns:
            Formatted conversations text
        """
        if not conversations:
            return ""
        
        # Define headers once - reordered with time fields first, then id
        headers = ["created_at", "updated_at", "conversation_id", "user_id", "private", "to_email", "from_email", "cc_email", "bcc_email"]
        
        conversations_lines = ["**— Conversations —**", '|'.join(headers)]
        
        for conv in conversations:
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
            
            # Format dates
            created_at = conv.get('created_at', 'N/A')
            updated_at = conv.get('updated_at', 'N/A')
            
            # Format privacy status
            is_private = conv.get('private', False)
            privacy_status = "private" if is_private else "public"
            
            # Get email fields
            to_emails = ', '.join(conv.get('to_emails', []))
            from_email = conv.get('from_email', 'N/A')
            cc_emails = ', '.join(conv.get('cc_emails', []))
            bcc_emails = ', '.join(conv.get('bcc_emails', []))
            
            # Get values - reordered to match headers
            values = [
                str(created_at),
                str(updated_at),
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
            
            conversations_lines.extend([
                '|'.join(values),
                "",  # Add blank line before body text
                body_text,
                "---",
                ""  # Add extra blank line for better readability
            ])
        
        return '\n'.join(conversations_lines)
    
    def _format_attachments_colon_separated(self, attachments: List[Dict[str, Any]], user_data: dict = None) -> str:
        """
        Format attachments in pipe-separated format (regardless of where they're stored).
        
        Args:
            attachments: List of attachment data
            user_data: User data for context
            
        Returns:
            Formatted attachments text
        """
        if not attachments:
            return ""
        
        # Define headers once - reordered with time fields first, then id
        headers = ["created_at", "updated_at", "attachment_id", "newNamed file name", "size", "user_id", "conversation_id"]
        
        attachment_lines = ["**— Attachment Details —**", '|'.join(headers)]
        
        for attachment in attachments:
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
            
            # Format attachment info
            attachment_id = attachment.get('id', 'N/A')
            original_name = attachment.get('name', 'N/A')
            new_name = f"{attachment_id}_{original_name}"  # attachmentId_nameofthefile
            
            # Get values - reordered to match headers
            values = [
                str(attachment.get('created_at', 'N/A')),
                str(attachment.get('updated_at', 'N/A')),
                str(attachment_id),
                str(new_name),
                str(attachment.get('size', 'N/A')),
                str(user_email),
                str(attachment.get('conversation_id', 'N/A'))
            ]
            
            attachment_lines.append('|'.join(values))
        
        return '\n'.join(attachment_lines)
    
    def _handle_description_overflow(self, full_description: str, max_length: int) -> Dict[str, str]:
        """
        Handle description overflow using additional_info fields sequentially.
        
        Args:
            full_description: The complete description text
            max_length: Maximum length per field
            
        Returns:
            Dictionary mapping field names to description chunks
        """
        overflow_mappings = {}
        
        if len(full_description) <= max_length:
            overflow_mappings["description"] = full_description
            return overflow_mappings
        
        # Split description into chunks
        chunks = self._split_description_data(full_description, max_length, 10)  # 10 additional fields available
        
        # Assign chunks to fields
        overflow_mappings["description"] = chunks[0] if chunks else ""
        
        # Use additional_info fields sequentially (first-come-first-served starting from 10357)
        additional_info_fields = [
            "customfield_10357", "customfield_10358", "customfield_10359", "customfield_10360",
            "customfield_10361", "customfield_10362", "customfield_10363", "customfield_10364",
            "customfield_10365", "customfield_10366"  # FD_additional_info1-10
        ]
        
        chunk_index = 1
        for field_id in additional_info_fields:
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
        
        # Look for section separators (double newlines or bold headers)
        # Find the last occurrence of double newline before max_length
        last_separator_pos = data.rfind('\n\n', 0, max_length)
        if last_separator_pos > 0:
            return last_separator_pos + 2
        
        # Look for bold headers (markdown format)
        last_bold_pos = data.rfind('**', 0, max_length)
        if last_bold_pos > max_length * 0.8:  # Only use if it's not too far from max_length
            return last_bold_pos
        
        # If no good separator found, break at max_length but try to break at a newline
        break_point = data.rfind('\n', 0, max_length)
        if break_point > max_length * 0.8:  # Only use newline if it's not too far from max_length
            return break_point + 1
        
        return max_length
    
    def _handle_conversation_overflow(self, conversation_data: str, original_field: str) -> Dict[str, str]:
        """
        Handle conversation overflow using dedicated conversation overflow fields.
        
        Args:
            conversation_data: The conversation data string
            original_field: The original field name
            
        Returns:
            Dictionary mapping field names to conversation chunks
        """
        overflow_mappings = {}
        max_length = 32000
        
        if len(conversation_data) <= max_length:
            overflow_mappings[original_field] = conversation_data
            return overflow_mappings
        
        # Split conversation data into chunks
        chunks = self._split_conversation_data(conversation_data, max_length)
        
        # First chunk goes to original field
        overflow_mappings[original_field] = chunks[0] if chunks else ""
        
        # Use dedicated conversation overflow fields
        conversation_overflow_fields = [
            "customfield_10355"   # FD_conversation2 (only one overflow field exists)
        ]
        
        chunk_index = 1
        for field_id in conversation_overflow_fields:
            if chunk_index < len(chunks):
                overflow_mappings[field_id] = chunks[chunk_index]
                chunk_index += 1
            else:
                break
        
        # If still more chunks, use additional_info fields
        additional_info_fields = [
            "customfield_10357", "customfield_10358", "customfield_10359", "customfield_10360",
            "customfield_10361", "customfield_10362", "customfield_10363", "customfield_10364",
            "customfield_10365", "customfield_10366"  # FD_additional_info1-10
        ]
        
        for field_id in additional_info_fields:
            if chunk_index < len(chunks):
                overflow_mappings[field_id] = chunks[chunk_index]
                chunk_index += 1
            else:
                break
        
        return overflow_mappings
    
    def _handle_attachment_overflow(self, attachment_data: str, original_field: str) -> Dict[str, str]:
        """
        Handle attachment overflow using dedicated attachment overflow fields.
        
        Args:
            attachment_data: The attachment data string
            original_field: The original field name
            
        Returns:
            Dictionary mapping field names to attachment chunks
        """
        overflow_mappings = {}
        max_length = 32000
        
        if len(attachment_data) <= max_length:
            overflow_mappings[original_field] = attachment_data
            return overflow_mappings
        
        # Split attachment data into chunks
        chunks = self._split_attachment_data(attachment_data, max_length)
        
        # First chunk goes to original field
        overflow_mappings[original_field] = chunks[0] if chunks else ""
        
        # Use dedicated attachment overflow field
        attachment_overflow_field = "customfield_10356"  # FD_attachments_details2
        
        chunk_index = 1
        if chunk_index < len(chunks):
            overflow_mappings[attachment_overflow_field] = chunks[chunk_index]
            chunk_index += 1
        
        # If still more chunks, use additional_info fields
        additional_info_fields = [
            "customfield_10357", "customfield_10358", "customfield_10359", "customfield_10360",
            "customfield_10361", "customfield_10362", "customfield_10363", "customfield_10364",
            "customfield_10365", "customfield_10366"  # FD_additional_info1-10
        ]
        
        for field_id in additional_info_fields:
            if chunk_index < len(chunks):
                overflow_mappings[field_id] = chunks[chunk_index]
                chunk_index += 1
            else:
                break
        
        return overflow_mappings
    
    def _split_conversation_data(self, data: str, max_length: int) -> List[str]:
        """
        Split conversation data into chunks for overflow fields.
        
        Args:
            data: Conversation data string
            max_length: Maximum length per field
            
        Returns:
            List of conversation chunks
        """
        if len(data) <= max_length:
            return [data]
        
        chunks = []
        remaining_data = data
        chunk_number = 1
        
        while remaining_data:
            if len(remaining_data) <= max_length:
                if chunk_number == 1:
                    chunks.append(remaining_data)
                else:
                    header = f"**— Conversations (Continued {chunk_number}) —**\n"
                    available_length = max_length - len(header)
                    if len(remaining_data) <= available_length:
                        chunks.append(header + remaining_data)
                    else:
                        break_point = self._find_conversation_break_point(remaining_data, available_length)
                        chunks.append(header + remaining_data[:break_point])
                        remaining_data = remaining_data[break_point:]
                        chunk_number += 1
                        continue
                break
            else:
                if chunk_number == 1:
                    # First chunk
                    break_point = self._find_conversation_break_point(remaining_data, max_length)
                    chunks.append(remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
                else:
                    # Subsequent chunks with header
                    header = f"**— Conversations (Continued {chunk_number}) —**\n"
                    available_length = max_length - len(header)
                    break_point = self._find_conversation_break_point(remaining_data, available_length)
                    chunks.append(header + remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
                
                chunk_number += 1
        
        return chunks
    
    def _split_attachment_data(self, data: str, max_length: int) -> List[str]:
        """
        Split attachment data into chunks for overflow fields.
        
        Args:
            data: Attachment data string
            max_length: Maximum length per field
            
        Returns:
            List of attachment chunks
        """
        if len(data) <= max_length:
            return [data]
        
        chunks = []
        remaining_data = data
        chunk_number = 1
        
        while remaining_data:
            if len(remaining_data) <= max_length:
                if chunk_number == 1:
                    chunks.append(remaining_data)
                else:
                    header = f"**— Attachments (Continued {chunk_number}) —**\n"
                    available_length = max_length - len(header)
                    if len(remaining_data) <= available_length:
                        chunks.append(header + remaining_data)
                    else:
                        break_point = self._find_attachment_break_point(remaining_data, available_length)
                        chunks.append(header + remaining_data[:break_point])
                        remaining_data = remaining_data[break_point:]
                        chunk_number += 1
                        continue
                break
            else:
                if chunk_number == 1:
                    # First chunk
                    break_point = self._find_attachment_break_point(remaining_data, max_length)
                    chunks.append(remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
                else:
                    # Subsequent chunks with header
                    header = f"**— Attachments (Continued {chunk_number}) —**\n"
                    available_length = max_length - len(header)
                    break_point = self._find_attachment_break_point(remaining_data, available_length)
                    chunks.append(header + remaining_data[:break_point])
                    remaining_data = remaining_data[break_point:]
                
                chunk_number += 1
        
        return chunks
    
    def _find_conversation_break_point(self, data: str, max_length: int) -> int:
        """
        Find a good break point in conversation data.
        
        Args:
            data: Conversation data string
            max_length: Maximum length for this chunk
            
        Returns:
            Index to break at
        """
        if len(data) <= max_length:
            return len(data)
        
        # Look for conversation separators (--- or double newlines)
        last_separator_pos = data.rfind('---', 0, max_length)
        if last_separator_pos > 0:
            return last_separator_pos + 3
        
        # Look for double newlines
        last_newline_pos = data.rfind('\n\n', 0, max_length)
        if last_newline_pos > 0:
            return last_newline_pos + 2
        
        # Fall back to single newline
        break_point = data.rfind('\n', 0, max_length)
        if break_point > max_length * 0.8:
            return break_point + 1
        
        return max_length
    
    def _find_attachment_break_point(self, data: str, max_length: int) -> int:
        """
        Find a good break point in attachment data.
        
        Args:
            data: Attachment data string
            max_length: Maximum length for this chunk
            
        Returns:
            Index to break at
        """
        if len(data) <= max_length:
            return len(data)
        
        # Look for attachment separators (newlines between attachment entries)
        last_newline_pos = data.rfind('\n', 0, max_length)
        if last_newline_pos > max_length * 0.8:
            return last_newline_pos + 1
        
        return max_length
