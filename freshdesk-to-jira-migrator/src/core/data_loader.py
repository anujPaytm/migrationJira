"""
Data loading utilities for Freshdesk export data.
Handles loading ticket details, conversations, attachments, and user data.
"""

import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path


class DataLoader:
    """
    Loads Freshdesk data from exported JSON files.
    """
    
    def __init__(self, data_directory: str = "../data_to_be_migrated"):
        """
        Initialize the data loader.
        
        Args:
            data_directory: Path to the data directory containing Freshdesk exports
        """
        self.data_directory = Path(data_directory)
        
        # Define subdirectories
        self.ticket_details_dir = self.data_directory / "ticket_details"
        self.conversations_dir = self.data_directory / "conversations"
        self.ticket_attachments_dir = self.data_directory / "ticket_attachments"
        self.conversation_attachments_dir = self.data_directory / "conversation_attachments"
        self.user_details_dir = self.data_directory / "user_details"
        self.attachments_dir = self.data_directory / "attachments"
        
        # Load user data once
        self._user_data = None
    
    def load_user_details(self) -> Dict[str, Any]:
        """
        Load all user data (agents, contacts, groups, products, email configs).
        
        Returns:
            Dictionary containing agents, contacts, groups, products, and email configs data
        """
        if self._user_data is not None:
            return self._user_data
        
        user_data = {
            "agents": {}, 
            "contacts": {}, 
            "groups": {}, 
            "products": {}, 
            "email_configs": {}
        }
        
        # Load agents
        agents_file = self.user_details_dir / "all_agents.json"
        if agents_file.exists():
            try:
                with open(agents_file, 'r', encoding='utf-8') as f:
                    agents_list = json.load(f)
                    # Convert to dictionary with ID as key
                    for agent in agents_list:
                        if 'id' in agent:
                            user_data["agents"][str(agent['id'])] = agent
            except Exception as e:
                print(f"Warning: Error loading agents data: {e}")
        
        # Load contacts
        contacts_file = self.user_details_dir / "all_contacts.json"
        if contacts_file.exists():
            try:
                with open(contacts_file, 'r', encoding='utf-8') as f:
                    contacts_list = json.load(f)
                    # Convert to dictionary with ID as key
                    for contact in contacts_list:
                        if 'id' in contact:
                            user_data["contacts"][str(contact['id'])] = contact
            except Exception as e:
                print(f"Warning: Error loading contacts data: {e}")
        
        # Load groups
        groups_file = self.user_details_dir / "all_groups.json"
        if groups_file.exists():
            try:
                with open(groups_file, 'r', encoding='utf-8') as f:
                    groups_list = json.load(f)
                    # Convert to dictionary with ID as key
                    for group in groups_list:
                        if 'id' in group:
                            user_data["groups"][str(group['id'])] = group
            except Exception as e:
                print(f"Warning: Error loading groups data: {e}")
        
        # Load products
        products_file = self.user_details_dir / "all_products.json"
        if products_file.exists():
            try:
                with open(products_file, 'r', encoding='utf-8') as f:
                    products_list = json.load(f)
                    # Convert to dictionary with ID as key
                    for product in products_list:
                        if 'id' in product:
                            user_data["products"][str(product['id'])] = product
            except Exception as e:
                print(f"Warning: Error loading products data: {e}")
        
        # Load email configs
        email_configs_file = self.user_details_dir / "all_email_configs.json"
        if email_configs_file.exists():
            try:
                with open(email_configs_file, 'r', encoding='utf-8') as f:
                    email_configs_list = json.load(f)
                    # Convert to dictionary with ID as key
                    for email_config in email_configs_list:
                        if 'id' in email_config:
                            user_data["email_configs"][str(email_config['id'])] = email_config
            except Exception as e:
                print(f"Warning: Error loading email configs data: {e}")
        
        self._user_data = user_data
        return user_data
    
    def load_ticket_details(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """
        Load ticket details for a specific ticket ID.
        
        Args:
            ticket_id: Freshdesk ticket ID
            
        Returns:
            Ticket details dictionary or None if not found
        """
        file_path = self.ticket_details_dir / f"ticket_{ticket_id}_details.json"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Ticket details file not found for ticket {ticket_id}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in ticket details file for ticket {ticket_id}: {e}")
            return None
    
    def load_conversations(self, ticket_id: int) -> List[Dict[str, Any]]:
        """
        Load conversations for a specific ticket ID.
        
        Args:
            ticket_id: Freshdesk ticket ID
            
        Returns:
            List of conversation dictionaries
        """
        file_path = self.conversations_dir / f"ticket_{ticket_id}_conversations.json"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Conversations file not found for ticket {ticket_id}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in conversations file for ticket {ticket_id}: {e}")
            return []
    
    def load_ticket_attachments(self, ticket_id: int) -> List[Dict[str, Any]]:
        """
        Load ticket attachments for a specific ticket ID.
        
        Args:
            ticket_id: Freshdesk ticket ID
            
        Returns:
            List of ticket attachment dictionaries
        """
        file_path = self.ticket_attachments_dir / f"ticket_{ticket_id}_attachments.json"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Ticket attachments file not found for ticket {ticket_id}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in ticket attachments file for ticket {ticket_id}: {e}")
            return []
    
    def load_conversation_attachments(self, ticket_id: int) -> List[Dict[str, Any]]:
        """
        Load conversation attachments for a specific ticket ID.
        
        Args:
            ticket_id: Freshdesk ticket ID
            
        Returns:
            List of conversation attachment dictionaries
        """
        file_path = self.conversation_attachments_dir / f"ticket_{ticket_id}_conversation_attachments.json"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Conversation attachments file not found for ticket {ticket_id}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in conversation attachments file for ticket {ticket_id}: {e}")
            return []
    
    def get_attachment_file_path(self, ticket_id: int, filename: str) -> Optional[str]:
        """
        Get the file path for an attachment.
        
        Args:
            ticket_id: Freshdesk ticket ID
            filename: Attachment filename
            
        Returns:
            Full file path or None if not found
        """
        # Try the original filename first
        file_path = self.attachments_dir / str(ticket_id) / filename
        
        if file_path.exists():
            return str(file_path)
        
        # For conversation attachments, try with 'conv_' prefix
        conv_filename = f"conv_{filename}"
        conv_file_path = self.attachments_dir / str(ticket_id) / conv_filename
        
        if conv_file_path.exists():
            return str(conv_file_path)
        
        return None
    
    def load_all_ticket_ids(self) -> List[int]:
        """
        Get all available ticket IDs from the ticket details directory.
        
        Returns:
            List of ticket IDs
        """
        ticket_ids = []
        
        if not self.ticket_details_dir.exists():
            print(f"Warning: Ticket details directory not found: {self.ticket_details_dir}")
            return ticket_ids
        
        for file_path in self.ticket_details_dir.glob("ticket_*_details.json"):
            try:
                # Extract ticket ID from filename like "ticket_52_details.json"
                filename = file_path.stem  # "ticket_52_details"
                ticket_id_str = filename.replace("ticket_", "").replace("_details", "")
                ticket_id = int(ticket_id_str)
                ticket_ids.append(ticket_id)
            except ValueError:
                print(f"Warning: Invalid ticket ID filename: {file_path.name}")
        
        return sorted(ticket_ids)
    
    def load_ticket_data(self, ticket_id: int) -> Dict[str, Any]:
        """
        Load all data for a specific ticket.
        
        Args:
            ticket_id: Freshdesk ticket ID
            
        Returns:
            Dictionary containing all ticket data
        """
        ticket_data = {
            "ticket_id": ticket_id,
            "ticket_details": None,
            "conversations": [],
            "ticket_attachments": [],
            "conversation_attachments": [],
            "user_data": {}
        }
        
        # Load ticket details
        ticket_details = self.load_ticket_details(ticket_id)
        if ticket_details:
            ticket_data["ticket_details"] = ticket_details
        
        # Load conversations
        conversations = self.load_conversations(ticket_id)
        ticket_data["conversations"] = conversations
        
        # Load attachments
        ticket_attachments = self.load_ticket_attachments(ticket_id)
        ticket_data["ticket_attachments"] = ticket_attachments
        
        conversation_attachments = self.load_conversation_attachments(ticket_id)
        ticket_data["conversation_attachments"] = conversation_attachments
        
        # Load user data (agents and contacts)
        user_data = self.load_user_details()
        ticket_data["user_data"] = user_data
        
        return ticket_data
    
    def validate_data_directory(self) -> bool:
        """
        Validate that the data directory structure is correct.
        
        Returns:
            True if valid, False otherwise
        """
        required_dirs = [
            self.ticket_details_dir,
            self.conversations_dir,
            self.ticket_attachments_dir,
            self.conversation_attachments_dir,
            self.user_details_dir,
            self.attachments_dir
        ]
        
        missing_dirs = []
        for dir_path in required_dirs:
            if not dir_path.exists():
                missing_dirs.append(str(dir_path))
        
        if missing_dirs:
            print(f"Error: Missing required directories: {missing_dirs}")
            return False
        
        return True
    
    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get a summary of available data.
        
        Returns:
            Data summary dictionary
        """
        ticket_ids = self.load_all_ticket_ids()
        user_data = self.load_user_details()
        
        summary = {
            "total_tickets": len(ticket_ids),
            "ticket_ids": ticket_ids[:10],  # First 10 for preview
            "data_directory": str(self.data_directory),
            "directories_exist": {
                "ticket_details": self.ticket_details_dir.exists(),
                "conversations": self.conversations_dir.exists(),
                "ticket_attachments": self.ticket_attachments_dir.exists(),
                "conversation_attachments": self.conversation_attachments_dir.exists(),
                "user_details": self.user_details_dir.exists(),
                "attachments": self.attachments_dir.exists()
            },
            "user_data": {
                "total_agents": len(user_data.get("agents", {})),
                "total_contacts": len(user_data.get("contacts", {})),
                "total_groups": len(user_data.get("groups", {})),
                "total_products": len(user_data.get("products", {})),
                "total_email_configs": len(user_data.get("email_configs", {}))
            }
        }
        
        return summary
