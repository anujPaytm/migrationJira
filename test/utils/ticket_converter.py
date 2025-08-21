import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from dateutil import parser

class TicketConverter:
    """Convert Freshdesk tickets to JIRA format"""
    
    def __init__(self, user_mapper):
        self.user_mapper = user_mapper
        
        # Priority mapping
        self.priority_map = {
            1: "Low",
            2: "Medium", 
            3: "High",
            4: "Highest"
        }
        
        # Status mapping
        self.status_map = {
            2: "To Do",
            3: "In Progress",
            4: "Done",
            5: "Done"
        }
        
        # Source mapping
        self.source_map = {
            1: "Email",
            2: "Portal",
            3: "Phone",
            4: "Chat",
            5: "Mobihelp",
            6: "Feedback Widget",
            7: "Outbound Email"
        }
    
    def clean_html(self, html_content: str) -> str:
        """Clean HTML content and extract text"""
        if not html_content:
            return ""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator='\n', strip=True)
    
    def format_ticket_metadata(self, ticket: Dict[str, Any]) -> str:
        """Format ALL ticket details metadata in metabase style"""
        metadata_lines = [
            "**— Freshdesk Ticket Metadata —**",
            f"id: {ticket.get('id', 'N/A')}",
            f"subject: {ticket.get('subject', 'N/A')}",
            f"priority: {self.priority_map.get(ticket.get('priority'), 'Unknown')}",
            f"status: {self.status_map.get(ticket.get('status'), 'Unknown')}",
            f"type: {ticket.get('type', 'N/A')}",
            f"source: {self.source_map.get(ticket.get('source'), 'Unknown')}",
            f"source_additional_info: {ticket.get('source_additional_info', 'N/A')}",
            f"cc_emails: {', '.join(ticket.get('cc_emails', []))}",
            f"fwd_emails: {', '.join(ticket.get('fwd_emails', []))}",
            f"reply_cc_emails: {', '.join(ticket.get('reply_cc_emails', []))}",
            f"ticket_cc_emails: {', '.join(ticket.get('ticket_cc_emails', []))}",
            f"ticket_bcc_emails: {', '.join(ticket.get('ticket_bcc_emails', []))}",
            f"to_emails: {', '.join(ticket.get('to_emails', []))}",
            f"support_email: {ticket.get('support_email', 'N/A')}",
            f"requester_id: {ticket.get('requester_id', 'N/A')}",
            f"responder_id: {ticket.get('responder_id', 'N/A')}",
            f"group_id: {ticket.get('group_id', 'N/A')}",
            f"company_id: {ticket.get('company_id', 'N/A')}",
            f"created_at: {ticket.get('created_at', 'N/A')}",
            f"updated_at: {ticket.get('updated_at', 'N/A')}",
            f"due_by: {ticket.get('due_by', 'N/A')}",
            f"fr_due_by: {ticket.get('fr_due_by', 'N/A')}",
            f"is_escalated: {ticket.get('is_escalated', False)}",
            f"fr_escalated: {ticket.get('fr_escalated', False)}",
            f"spam: {ticket.get('spam', False)}",
            f"email_config_id: {ticket.get('email_config_id', 'N/A')}",
            f"product_id: {ticket.get('product_id', 'N/A')}",
            f"association_type: {ticket.get('association_type', 'N/A')}",
            f"tags: {', '.join(ticket.get('tags', []))}",
            f"sentiment_score: {ticket.get('sentiment_score', 'N/A')}",
            f"initial_sentiment_score: {ticket.get('initial_sentiment_score', 'N/A')}",
            f"structured_description: {ticket.get('structured_description', 'N/A')}",
            f"nr_due_by: {ticket.get('nr_due_by', 'N/A')}",
            f"nr_escalated: {ticket.get('nr_escalated', False)}",
            f"ticket_id: {ticket.get('ticket_id', 'N/A')}"
        ]
        
        # Add custom fields if any
        custom_fields = ticket.get('custom_fields', {})
        for key, value in custom_fields.items():
            metadata_lines.append(f"{key}: {value}")
        
        return '\n'.join(metadata_lines)
    
    def format_description(self, ticket: Dict[str, Any]) -> str:
        """Format ticket description separately"""
        description_text = ticket.get('description_text', 'N/A')
        if description_text and description_text != 'N/A':
            return f"**— Description —**\n{description_text}"
        return ""
    
    def format_conversations(self, conversations: List[Dict[str, Any]]) -> str:
        """Format conversations with detailed information"""
        if not conversations:
            return ""
        
        # Define headers once - reordered with time fields first, then id
        headers = ["created_at", "updated_at", "conversation_id", "user_id", "private", "to_email", "from_email", "cc_email", "bcc_email"]
        
        conversations_lines = ["**— Conversations —**", ':'.join(headers)]
        
        for conv in conversations:
            # Get user information
            user_info = self.user_mapper.get_conversation_author(conv)
            user_email = user_info.get('email', 'NA') if user_info else 'NA'
            
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
            
            # Clean the body text
            body_text = conv.get('body_text', '') or self.clean_html(conv.get('body', ''))
            
            conversations_lines.extend([
                ':'.join(values),
                "",  # Add blank line before body text
                body_text,
                "---",
                ""  # Add extra blank line for better readability
            ])
        
        return '\n'.join(conversations_lines)
    
    def format_attachment_details(self, ticket_attachments: List[Dict[str, Any]], conversation_attachments: List[Dict[str, Any]]) -> str:
        """Format attachment details"""
        if not ticket_attachments and not conversation_attachments:
            return ""
        
        # Define headers once - reordered with time fields first, then id
        headers = ["created_at", "updated_at", "attachment_id", "newNamed file name", "size", "user_id", "conversation_id"]
        
        attachment_lines = ["**— Attachment Details —**", ':'.join(headers)]
        
        # Process ticket attachments
        for attachment in ticket_attachments:
            # Get user information
            user_info = self.user_mapper.get_user_by_id(attachment.get('user_id'))
            user_email = user_info.get('email', 'NA') if user_info else 'NA'
            
            # Format attachment info
            attachment_id = attachment.get('id', 'N/A')
            original_name = attachment.get('name', 'N/A')
            new_name = f"{attachment_id}_{original_name}"
            
            # Get values - reordered to match headers
            values = [
                str(attachment.get('created_at', 'N/A')),
                'NA',  # updated_at is NA for ticket attachments
                str(attachment_id),
                str(new_name),
                str(attachment.get('size', 'N/A')),
                str(user_email),
                'NA'  # conversation_id is NA for ticket attachments
            ]
            
            attachment_lines.append(':'.join(values))
        
        # Process conversation attachments
        for attachment in conversation_attachments:
            # Get user information
            user_info = self.user_mapper.get_user_by_id(attachment.get('user_id'))
            user_email = user_info.get('email', 'NA') if user_info else 'NA'
            
            # Format attachment info
            attachment_id = attachment.get('id', 'N/A')
            original_name = attachment.get('name', 'N/A')
            new_name = f"{attachment_id}_{original_name}"
            
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
    
    def convert_to_jira_issue(self, ticket: Dict[str, Any], conversations: List[Dict[str, Any]] = None, 
                             ticket_attachments: List[Dict[str, Any]] = None, 
                             conversation_attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Convert Freshdesk ticket to JIRA issue format"""
        
        # Get user information
        requester = self.user_mapper.get_requester_info(ticket.get('requester_id'))
        responder = self.user_mapper.get_responder_info(ticket.get('responder_id'))
        
        # Format all sections
        ticket_metadata = self.format_ticket_metadata(ticket)
        description_section = self.format_description(ticket)
        conversations_section = self.format_conversations(conversations or [])
        attachment_details = self.format_attachment_details(ticket_attachments or [], conversation_attachments or [])
        
        # Combine all sections with proper spacing
        sections = []
        if ticket_metadata:
            sections.append(ticket_metadata)
        if description_section:
            sections.append(description_section)
        if conversations_section:
            sections.append(conversations_section)
        if attachment_details:
            sections.append(attachment_details)
        
        full_description = '\n\n\n'.join(sections)  # Triple line spacing between sections
        
        # Truncate description if it exceeds JIRA's 32,767 character limit
        max_description_length = 32000  # Leave some buffer
        if len(full_description) > max_description_length:
            print(f"Warning: Description too long ({len(full_description)} chars), truncating to {max_description_length} chars")
            
            # Keep ticket metadata and truncate conversations
            truncated_description = ticket_metadata + "\n\n"
            remaining_length = max_description_length - len(truncated_description) - 100  # Leave space for truncation notice
            
            # Add truncated conversations
            if conversations_section:
                truncated_conversations = conversations_section[:remaining_length]
                if len(conversations_section) > remaining_length:
                    truncated_conversations += "\n\n[TRUNCATED - Description too long for JIRA]"
                truncated_description += truncated_conversations
            
            # Add attachment details if space allows
            if attachment_details and len(truncated_description) + len(attachment_details) < max_description_length:
                truncated_description += "\n\n" + attachment_details
            
            full_description = truncated_description
        
        # Parse dates
        due_date = None
        if ticket.get('due_by'):
            try:
                due_date = parser.parse(ticket['due_by']).strftime('%Y-%m-%d')
            except:
                pass
        
        # Build JIRA issue
        jira_issue = {
            "fields": {
                "project": {"key": "FTJM"},
                "summary": f"Freshdesk Ticket #{ticket.get('id')}: {ticket.get('subject', 'No Subject')}",
                "description": full_description,
                "issuetype": {"name": "Task"},
                "priority": {"name": self.priority_map.get(ticket.get('priority', 1), "Low")}
            }
        }
        
        # Add assignee if responder exists, otherwise use current user for testing
        if responder and responder.get('email'):
            # For testing, use current user since responder might not exist in JIRA
            jira_issue["fields"]["assignee"] = {"emailAddress": "t-anuj.tewari@ocltp.com"}
        else:
            # Use current user as assignee if no responder found
            jira_issue["fields"]["assignee"] = {"emailAddress": "t-anuj.tewari@ocltp.com"}
        
        # Skip reporter field - JIRA will use current user as default reporter
        
        # Add due date
        if due_date:
            jira_issue["fields"]["duedate"] = due_date
        
        # Add Freshdesk custom fields
        jira_issue["fields"]["customfield_10289"] = self.priority_map.get(ticket.get('priority', 1), "Low")  # FD_Priority
        jira_issue["fields"]["customfield_10290"] = ticket.get('created_at', '')  # FD_Created_At
        jira_issue["fields"]["customfield_10291"] = ticket.get('updated_at', '')  # FD_Updated_At
        jira_issue["fields"]["customfield_10294"] = self.status_map.get(ticket.get('status', 2), "Open")  # FD_Status
        jira_issue["fields"]["customfield_10295"] = ticket.get('type', '') or 'Task'  # FD_IssueType
        
        # Add Freshdesk user information - ONLY EMAIL ADDRESSES
        if requester:
            jira_issue["fields"]["customfield_10292"] = requester.get('email', '')  # FD_Reporter
        
        if responder:
            jira_issue["fields"]["customfield_10293"] = responder.get('email', '')  # FD_Assignee
        else:
            jira_issue["fields"]["customfield_10293"] = ""  # FD_Assignee
        
        return jira_issue
    
    def get_priority_name(self, priority: int) -> str:
        """Get priority name from priority number"""
        return self.priority_map.get(priority, "Low")
    
    def get_status_name(self, status: int) -> str:
        """Get status name from status number"""
        return self.status_map.get(status, "To Do")
