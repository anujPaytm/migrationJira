import json
import os
from typing import Dict, List, Any
from pathlib import Path

class DataLoader:
    """Load Freshdesk data from JSON files"""
    
    def __init__(self, data_path: str = "../data_to_be_migrated"):
        self.data_path = Path(data_path)
        
    def load_ticket_details(self, ticket_id: int = None) -> Dict[str, Any]:
        """Load ticket details"""
        if ticket_id:
            file_path = self.data_path / "ticket_details" / f"ticket_{ticket_id}_details.json"
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        
        # Load all ticket details
        tickets = {}
        ticket_dir = self.data_path / "ticket_details"
        for file_path in ticket_dir.glob("ticket_*_details.json"):
            ticket_id = int(file_path.stem.split('_')[1])
            with open(file_path, 'r', encoding='utf-8') as f:
                tickets[ticket_id] = json.load(f)
        return tickets
    
    def load_conversations(self, ticket_id: int = None) -> Dict[str, List[Dict]]:
        """Load conversations for tickets"""
        conversations = {}
        conv_dir = self.data_path / "conversations"
        
        if ticket_id:
            file_path = conv_dir / f"ticket_{ticket_id}_conversations.json"
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return {ticket_id: json.load(f)}
            return {}
        
        # Load all conversations
        for file_path in conv_dir.glob("ticket_*_conversations.json"):
            ticket_id = int(file_path.stem.split('_')[1])
            with open(file_path, 'r', encoding='utf-8') as f:
                conversations[ticket_id] = json.load(f)
        return conversations
    
    def load_ticket_attachments(self, ticket_id: int = None) -> Dict[str, List[Dict]]:
        """Load ticket attachments"""
        attachments = {}
        attach_dir = self.data_path / "ticket_attachments"
        
        if ticket_id:
            file_path = attach_dir / f"ticket_{ticket_id}_attachments.json"
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return {ticket_id: json.load(f)}
            return {}
        
        # Load all attachments
        for file_path in attach_dir.glob("ticket_*_attachments.json"):
            ticket_id = int(file_path.stem.split('_')[1])
            with open(file_path, 'r', encoding='utf-8') as f:
                attachments[ticket_id] = json.load(f)
        return attachments
    
    def load_conversation_attachments(self, ticket_id: int = None) -> Dict[str, List[Dict]]:
        """Load conversation attachments"""
        attachments = {}
        attach_dir = self.data_path / "conversation_attachments"
        
        if ticket_id:
            file_path = attach_dir / f"ticket_{ticket_id}_conversation_attachments.json"
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return {ticket_id: json.load(f)}
            return {}
        
        # Load all conversation attachments
        for file_path in attach_dir.glob("ticket_*_conversation_attachments.json"):
            ticket_id = int(file_path.stem.split('_')[1])
            with open(file_path, 'r', encoding='utf-8') as f:
                attachments[ticket_id] = json.load(f)
        return attachments
    
    def load_users(self) -> Dict[str, Any]:
        """Load user data (agents and contacts)"""
        users = {}
        
        # Load agents
        agents_file = self.data_path / "user_details" / "all_agents.json"
        if agents_file.exists():
            with open(agents_file, 'r', encoding='utf-8') as f:
                users['agents'] = json.load(f)
        
        # Load contacts
        contacts_file = self.data_path / "user_details" / "all_contacts.json"
        if contacts_file.exists():
            with open(contacts_file, 'r', encoding='utf-8') as f:
                users['contacts'] = json.load(f)
        
        return users
    
    def get_attachment_files(self, ticket_id: int) -> List[str]:
        """Get list of attachment files for a ticket"""
        attach_dir = self.data_path / "attachments" / str(ticket_id)
        if not attach_dir.exists():
            return []
        
        files = []
        for file_path in attach_dir.iterdir():
            if file_path.is_file():
                files.append(str(file_path))
        return files
