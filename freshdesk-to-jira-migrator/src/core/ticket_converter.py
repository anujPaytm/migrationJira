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
        
        # Build description using hierarchical approach
        description_parts = []
        
        # Add original description if available (only description_text, no HTML)
        if ticket.get('description_text'):
            description_parts.append(f"**— Description —**\n{ticket['description_text']}")
        
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
            
            # Format conversations in colon-separated format (regardless of where they're stored)
            formatted_conversations = self._format_conversations_colon_separated(conversations, user_data)
            
            # Add mapped conversation fields to JIRA issue
            for field_name, field_value in conv_mapped_fields.items():
                jira_issue["fields"][field_name] = field_value
            
            # Add unmapped conversations to description
            if conv_unmapped_fields and formatted_conversations:
                description_parts.append(formatted_conversations)
        
        # Map attachments using hierarchical approach
        all_attachments = ticket_attachments + conversation_attachments if ticket_attachments and conversation_attachments else (ticket_attachments or conversation_attachments or [])
        
        if all_attachments:
            att_mapped_fields, att_unmapped_fields = self.field_mapper.map_hierarchical_fields(all_attachments, "attachment_fields", user_data)
            
            # Format attachments in colon-separated format (regardless of where they're stored)
            formatted_attachments = self._format_attachments_colon_separated(all_attachments, user_data)
            
            # Add mapped attachment fields to JIRA issue
            for field_name, field_value in att_mapped_fields.items():
                jira_issue["fields"][field_name] = field_value
            
            # Add unmapped attachments to description
            if att_unmapped_fields and formatted_attachments:
                description_parts.append(formatted_attachments)
        
        # Combine all description parts
        if description_parts:
            full_description = '\n\n'.join(description_parts)
            
            # Truncate description if it exceeds JIRA's 32,767 character limit
            max_description_length = 32000  # Leave some buffer
            if len(full_description) > max_description_length:
                print(f"Warning: Description too long ({len(full_description)} chars), truncating to {max_description_length} chars")
                
                # Keep metadata and truncate conversations
                if len(description_parts) > 1:
                    truncated_description = description_parts[0] + "\n\n"  # Keep first part (metadata)
                    remaining_length = max_description_length - len(truncated_description) - 100
                    
                    # Add truncated conversations if any
                    if len(description_parts) > 1:
                        for part in description_parts[1:]:
                            if len(truncated_description) + len(part) < remaining_length:
                                truncated_description += part + "\n\n"
                            else:
                                truncated_description += part[:remaining_length - len(truncated_description)]
                                truncated_description += "\n\n[TRUNCATED - Description too long for JIRA]"
                                break
                    
                    full_description = truncated_description
                else:
                    full_description = truncate_text(full_description, max_description_length)
            
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
        Format conversations in colon-separated format (regardless of where they're stored).
        
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
        
        conversations_lines = ["**— Conversations —**", ':'.join(headers)]
        
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
                ':'.join(values),
                "",  # Add blank line before body text
                body_text,
                "---",
                ""  # Add extra blank line for better readability
            ])
        
        return '\n'.join(conversations_lines)
    
    def _format_attachments_colon_separated(self, attachments: List[Dict[str, Any]], user_data: dict = None) -> str:
        """
        Format attachments in colon-separated format (regardless of where they're stored).
        
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
        
        attachment_lines = ["**— Attachment Details —**", ':'.join(headers)]
        
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
            
            attachment_lines.append(':'.join(values))
        
        return '\n'.join(attachment_lines)
