"""
Ticket conversion logic for transforming Freshdesk tickets to JIRA issues.
Handles field mapping, description formatting, and custom field assignment.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import re
from bs4 import BeautifulSoup
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
    
    def html_to_plain_text(self, html_content: str) -> str:
        """
        Convert HTML content to plain text while preserving formatting and structure.
        This extracts the actual content from HTML tags, not the tags themselves.
        
        Args:
            html_content: HTML content to convert
            
        Returns:
            Plain text with preserved formatting and structure
        """
        if not html_content or not html_content.strip():
            return ""
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Handle line breaks
        for br in soup.find_all(['br', 'br/']):
            br.replace_with('\n')
        
        # Handle paragraphs
        for p in soup.find_all('p'):
            if p.get_text().strip():
                p.replace_with(p.get_text().strip() + '\n\n')
            else:
                p.decompose()
        
        # Handle bold text - make it stand out (JIRA uses *text* for bold)
        for tag in soup.find_all(['b', 'strong']):
            text = tag.get_text().strip()
            if text:
                tag.replace_with(f' *{text}* ')
            else:
                tag.decompose()
        
        # Handle italic text (JIRA uses _text_ for italic)
        for tag in soup.find_all(['i', 'em']):
            text = tag.get_text().strip()
            if text:
                tag.replace_with(f' _{text}_ ')
            else:
                tag.decompose()
        
        # Handle links - show text and URL
        for link in soup.find_all('a'):
            href = link.get('href', '')
            text = link.get_text()
            if href and href.startswith('mailto:'):
                # Keep email addresses as they are
                link.replace_with(text)
            elif href:
                # Show text and URL
                link.replace_with(f'{text} ({href})')
            else:
                link.replace_with(text)
        
        # Handle tables - convert to JIRA table format
        for table in soup.find_all('table'):
            table_text = '\n'
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    # Add header formatting with JIRA table syntax
                    if row.find('th'):
                        row_text = '||' + '||'.join([f'*{cell.get_text().strip()}*' for cell in cells]) + '||'
                    else:
                        row_text = '||' + '||'.join([cell.get_text().strip() for cell in cells]) + '||'
                    table_text += row_text + '\n'
            table_text += '\n'
            table.replace_with(table_text)
        
        # Handle images - show descriptive text
        for img in soup.find_all('img'):
            src = img.get('src', '')
            alt = img.get('alt', 'Image')
            if src:
                img.replace_with(f'[Image: {alt}] - URL: {src}')
            else:
                img.replace_with(f'[Image: {alt}]')
        
        # Handle lists
        for ul in soup.find_all('ul'):
            list_text = '\n'
            for li in ul.find_all('li'):
                list_text += f'• {li.get_text().strip()}\n'
            list_text += '\n'
            ul.replace_with(list_text)
        
        for ol in soup.find_all('ol'):
            list_text = '\n'
            for i, li in enumerate(ol.find_all('li'), 1):
                list_text += f'{i}. {li.get_text().strip()}\n'
            list_text += '\n'
            ol.replace_with(list_text)
        
        # Handle headers
        for i in range(1, 7):
            for h in soup.find_all(f'h{i}'):
                prefix = '#' * i + ' '
                h.replace_with(f'{prefix}{h.get_text().strip()}\n\n')
        
        # Handle blockquotes (email quotes) - convert > to proper quote format
        for blockquote in soup.find_all('blockquote'):
            lines = blockquote.get_text().strip().split('\n')
            quoted_text = '\n'.join([f'> {line}' for line in lines if line.strip()])
            blockquote.replace_with(f'\n{quoted_text}\n\n')
        
        # Handle code blocks
        for pre in soup.find_all('pre'):
            code_text = pre.get_text().strip()
            pre.replace_with(f'\n```\n{code_text}\n```\n\n')
        
        # Handle inline code
        for code in soup.find_all('code'):
            code_text = code.get_text().strip()
            code.replace_with(f'`{code_text}`')
        
        # Also handle any remaining > symbols that might be from email quotes
        # Replace standalone > symbols with proper quote format
        text = soup.get_text()
        
        # Clean up extra whitespace and newlines
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Remove multiple empty lines
        text = re.sub(r'[ \t]+', ' ', text)  # Normalize spaces
        text = re.sub(r'\n{3,}', '\n\n', text)  # Limit consecutive newlines to 2
        
        # Handle email quote symbols that might interfere with JIRA formatting
        # Simply remove problematic > symbols that break formatting
        text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)  # Remove > at start of lines
        text = re.sub(r'\n>\s*', '\n', text)  # Remove > after newlines
        text = re.sub(r'\s*>\s*', ' ', text)  # Remove standalone > symbols with spaces
        
        # Fix email headers formatting - put each header on its own line
        # Handle bold email headers first - use exact pattern matching
        text = re.sub(r'(\s+)\*From:\*(\s+)', r'\n\n*From:* ', text)
        text = re.sub(r'(\s+)\*To:\*(\s+)', r'\n\n*To:* ', text)
        text = re.sub(r'(\s+)\*Cc:\*(\s+)', r'\n\n*Cc:* ', text)
        text = re.sub(r'(\s+)\*Bcc:\*(\s+)', r'\n\n*Bcc:* ', text)
        text = re.sub(r'(\s+)\*Subject:\*(\s+)', r'\n\n*Subject:* ', text)
        text = re.sub(r'(\s+)\*Sent:\*(\s+)', r'\n\n*Sent:* ', text)
        text = re.sub(r'(\s+)\*Date:\*(\s+)', r'\n\n*Date:* ', text)
        
        # Handle regular email headers
        text = re.sub(r'(\s+)From:(\s+)', r'\n\nFrom: ', text)
        text = re.sub(r'(\s+)To:(\s+)', r'\n\nTo: ', text)
        text = re.sub(r'(\s+)Cc:(\s+)', r'\n\nCc: ', text)
        text = re.sub(r'(\s+)Bcc:(\s+)', r'\n\nBcc: ', text)
        text = re.sub(r'(\s+)Subject:(\s+)', r'\n\nSubject: ', text)
        text = re.sub(r'(\s+)Sent:(\s+)', r'\n\nSent: ', text)
        text = re.sub(r'(\s+)Date:(\s+)', r'\n\nDate: ', text)
        
        # Add single line separators between different email conversations
        # Look for patterns that indicate new email threads
        text = re.sub(r'\n\s*\*From:\*', '\n\n*From:*', text)
        text = re.sub(r'\n\s*From:', '\n\nFrom:', text)
        
        # Clean up multiple consecutive separators
        text = re.sub(r'--- NEW EMAIL ---\s*\n\s*--- NEW EMAIL ---', '--- NEW EMAIL ---', text)
        
        # Ensure proper spacing around email content
        text = re.sub(r'\n{3,}', '\n\n', text)  # Limit consecutive newlines to 2
        
        text = text.strip()
        
        return text
    
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
        
        # Add original description if available (convert HTML to readable plain text)
        description_html = ticket.get('description', '')
        if description_html:
            # Convert HTML to plain text while preserving formatting
            plain_text_description = self.html_to_plain_text(description_html)
            description_parts.append(f"**— Description —**\n{plain_text_description}")
        
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
            
            # Add all mapped fields (overflow is handled by field mapper)
            for field_name, field_value in conv_mapped_fields.items():
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
            
            # Add all mapped fields (overflow is handled by field mapper)
            for field_name, field_value in att_mapped_fields.items():
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
                
                # Use field mapper's overflow handling instead of hardcoded fields
                full_description = '\n\n'.join(description_parts)
                overflow_mappings = self.field_mapper.handle_description_overflow(full_description, max_description_length)
                
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
            issue_type: Issue type name or ID
        """
        # Check if issue_type is a numeric ID
        if issue_type.isdigit():
            jira_issue["fields"]["issuetype"]["id"] = issue_type
        else:
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
