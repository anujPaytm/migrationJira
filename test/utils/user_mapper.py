from typing import Dict, List, Optional, Any

class UserMapper:
    """Map Freshdesk users to JIRA users"""
    
    def __init__(self, users_data: Dict[str, Any]):
        self.agents = users_data.get('agents', [])
        self.contacts = users_data.get('contacts', [])
        
        # Create lookup dictionaries
        self.agents_by_id = {agent['id']: agent for agent in self.agents}
        self.contacts_by_id = {contact['id']: contact for contact in self.contacts}
        
    def get_requester_info(self, requester_id: int) -> Optional[Dict[str, str]]:
        """Get requester information by ID"""
        if requester_id in self.contacts_by_id:
            contact = self.contacts_by_id[requester_id]
            return {
                'name': contact.get('name', 'Unknown'),
                'email': contact.get('email', ''),
                'id': contact['id']
            }
        return None
    
    def get_responder_info(self, responder_id: int) -> Optional[Dict[str, str]]:
        """Get responder information by ID - search in both agents and contacts"""
        # Check if it's an agent first
        if responder_id in self.agents_by_id:
            agent = self.agents_by_id[responder_id]
            contact = agent.get('contact', {})
            return {
                'name': contact.get('name', 'Unknown'),
                'email': contact.get('email', ''),
                'id': agent['id'],
                'type': 'agent'
            }
        # Check if it's a contact
        elif responder_id in self.contacts_by_id:
            contact = self.contacts_by_id[responder_id]
            return {
                'name': contact.get('name', 'Unknown'),
                'email': contact.get('email', ''),
                'id': contact['id'],
                'type': 'contact'
            }
        return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, str]]:
        """Get user information by email"""
        # Check agents first
        for agent in self.agents:
            if agent.get('contact', {}).get('email') == email:
                contact = agent['contact']
                return {
                    'name': contact.get('name', 'Unknown'),
                    'email': contact.get('email', ''),
                    'id': agent['id'],
                    'type': 'agent'
                }
        
        # Check contacts
        for contact in self.contacts:
            if contact.get('email') == email:
                return {
                    'name': contact.get('name', 'Unknown'),
                    'email': contact.get('email', ''),
                    'id': contact['id'],
                    'type': 'contact'
                }
        
        return None
    
    def get_conversation_author(self, conversation: Dict) -> Optional[Dict[str, str]]:
        """Get conversation author information"""
        user_id = conversation.get('user_id')
        if user_id:
            # Check if it's an agent
            if user_id in self.agents_by_id:
                agent = self.agents_by_id[user_id]
                contact = agent.get('contact', {})
                return {
                    'name': contact.get('name', 'Unknown'),
                    'email': contact.get('email', ''),
                    'id': agent['id'],
                    'type': 'agent'
                }
            # Check if it's a contact
            elif user_id in self.contacts_by_id:
                contact = self.contacts_by_id[user_id]
                return {
                    'name': contact.get('name', 'Unknown'),
                    'email': contact.get('email', ''),
                    'id': contact['id'],
                    'type': 'contact'
                }
        
        return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, str]]:
        """Get user information by ID - search in both agents and contacts"""
        if user_id:
            # Check if it's an agent
            if user_id in self.agents_by_id:
                agent = self.agents_by_id[user_id]
                contact = agent.get('contact', {})
                return {
                    'name': contact.get('name', 'Unknown'),
                    'email': contact.get('email', ''),
                    'id': agent['id'],
                    'type': 'agent'
                }
            # Check if it's a contact
            elif user_id in self.contacts_by_id:
                contact = self.contacts_by_id[user_id]
                return {
                    'name': contact.get('name', 'Unknown'),
                    'email': contact.get('email', ''),
                    'id': contact['id'],
                    'type': 'contact'
                }
        
        return None
