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
    
    def format_metadata(self, ticket: Dict[str, Any]) -> str:
        """Format ticket metadata in metabase style"""
        metadata_lines = [
            "— Freshdesk Metadata —",
            f"id: {ticket.get('id', 'N/A')}",
            f"created_at: {ticket.get('created_at', 'N/A')}",
            f"updated_at: {ticket.get('updated_at', 'N/A')}",
            f"source: {self.source_map.get(ticket.get('source'), 'Unknown')}",
            f"product_id: {ticket.get('product_id', 'N/A')}",
            f"fr_due_by: {ticket.get('fr_due_by', 'N/A')}",
            f"fr_escalated: {ticket.get('fr_escalated', False)}",
            f"is_escalated: {ticket.get('is_escalated', False)}",
            f"spam: {ticket.get('spam', False)}",
            f"email_config_id: {ticket.get('email_config_id', 'N/A')}",
            f"priority: {ticket.get('priority', 'N/A')}",
            f"status: {ticket.get('status', 'N/A')}",
            f"group_id: {ticket.get('group_id', 'N/A')}",
            f"company_id: {ticket.get('company_id', 'N/A')}",
            f"type: {ticket.get('type', 'N/A')}",
            f"due_by: {ticket.get('due_by', 'N/A')}",
            f"nr_due_by: {ticket.get('nr_due_by', 'N/A')}",
            f"nr_escalated: {ticket.get('nr_escalated', False)}",
            f"sentiment_score: {ticket.get('sentiment_score', 'N/A')}",
            f"initial_sentiment_score: {ticket.get('initial_sentiment_score', 'N/A')}"
        ]
        
        # Add custom fields
        custom_fields = ticket.get('custom_fields', {})
        for key, value in custom_fields.items():
            metadata_lines.append(f"{key}: {value}")
        
        # Add tags
        tags = ticket.get('tags', [])
        if tags:
            metadata_lines.append(f"tags: {', '.join(tags)}")
        
        return '\n'.join(metadata_lines)
    
    def format_comments(self, conversations: List[Dict[str, Any]]) -> str:
        """Format conversations as comments"""
        if not conversations:
            return ""
        
        comments_lines = ["— Comments —"]
        
        for conv in conversations:
            author = self.user_mapper.get_conversation_author(conv)
            author_name = author.get('name', 'Unknown') if author else 'Unknown'
            author_email = author.get('email', '') if author else ''
            
            created_at = conv.get('created_at', '')
            if created_at:
                try:
                    dt = parser.parse(created_at)
                    created_at = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            
            # Clean the comment body
            body = conv.get('body_text', '') or self.clean_html(conv.get('body', ''))
            
            comments_lines.extend([
                f"\n**{author_name}** ({author_email}) - {created_at}",
                f"{body}",
                "---"
            ])
        
        return '\n'.join(comments_lines)
    
    def convert_to_jira_issue(self, ticket: Dict[str, Any], conversations: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Convert Freshdesk ticket to JIRA issue format"""
        
        # Get user information
        requester = self.user_mapper.get_requester_info(ticket.get('requester_id'))
        responder = self.user_mapper.get_responder_info(ticket.get('responder_id'))
        
        # Format description
        metadata = self.format_metadata(ticket)
        description = self.clean_html(ticket.get('description', ''))
        comments = self.format_comments(conversations or [])
        
        full_description = f"{metadata}\n\n— Description —\n{description}\n\n{comments}"
        
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
        jira_issue["fields"]["customfield_10289"] = str(ticket.get('priority', ''))  # FD_Priority
        jira_issue["fields"]["customfield_10290"] = ticket.get('created_at', '')  # FD_Created_At
        jira_issue["fields"]["customfield_10291"] = ticket.get('updated_at', '')  # FD_Updated_At
        jira_issue["fields"]["customfield_10294"] = str(ticket.get('status', ''))  # FD_Status
        jira_issue["fields"]["customfield_10295"] = ticket.get('type', '') or 'Task'  # FD_IssueType
        
        # Add Freshdesk user information
        if requester:
            jira_issue["fields"]["customfield_10292"] = f"{requester.get('name', '')} ({requester.get('email', '')})"  # FD_Reporter
        
        if responder:
            jira_issue["fields"]["customfield_10293"] = f"{responder.get('name', '')} ({responder.get('email', '')})"  # FD_Assignee
        else:
            jira_issue["fields"]["customfield_10293"] = "Unassigned"  # FD_Assignee
        
        # Add email fields and other Freshdesk data
        # Note: These would need custom field IDs to be created in JIRA first
        # For now, we'll add them to the description metadata
        email_fields = []
        if ticket.get('to_emails'):
            email_fields.append(f"To: {', '.join(ticket['to_emails'])}")
        if ticket.get('cc_emails'):
            email_fields.append(f"CC: {', '.join(ticket['cc_emails'])}")
        if ticket.get('fwd_emails'):
            email_fields.append(f"Forward: {', '.join(ticket['fwd_emails'])}")
        if ticket.get('reply_cc_emails'):
            email_fields.append(f"Reply CC: {', '.join(ticket['reply_cc_emails'])}")
        if ticket.get('ticket_cc_emails'):
            email_fields.append(f"Ticket CC: {', '.join(ticket['ticket_cc_emails'])}")
        if ticket.get('ticket_bcc_emails'):
            email_fields.append(f"Ticket BCC: {', '.join(ticket['ticket_bcc_emails'])}")
        if ticket.get('support_email'):
            email_fields.append(f"Support: {ticket['support_email']}")
        
        if email_fields:
            # Add email information to the description
            email_section = "\n— Email Information —\n" + "\n".join(email_fields)
            full_description = full_description.replace("— Description —", f"{email_section}\n\n— Description —")
            jira_issue["fields"]["description"] = full_description
        
        return jira_issue
    
    def get_priority_name(self, priority: int) -> str:
        """Get priority name from priority number"""
        return self.priority_map.get(priority, "Low")
    
    def get_status_name(self, status: int) -> str:
        """Get status name from status number"""
        return self.status_map.get(status, "To Do")
