import os
import requests
import tempfile
from typing import List, Dict, Optional
from pathlib import Path
import mimetypes

class AttachmentHandler:
    """Handle attachment downloads and uploads"""
    
    def __init__(self, jira_client):
        self.jira = jira_client
        self.temp_dir = tempfile.mkdtemp()
    
    def download_attachment(self, url: str, filename: str) -> Optional[str]:
        """Download attachment from URL"""
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            file_path = os.path.join(self.temp_dir, filename)
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return file_path
        except Exception as e:
            print(f"Failed to download attachment {filename}: {e}")
            return None
    
    def upload_attachment_to_jira(self, issue_key: str, file_path: str) -> bool:
        """Upload attachment to JIRA issue"""
        try:
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                return False
            
            with open(file_path, 'rb') as f:
                self.jira.add_attachment(issue_key, f, filename=os.path.basename(file_path))
            
            return True
        except Exception as e:
            print(f"Failed to upload attachment {file_path}: {e}")
            return False
    
    def get_local_attachment_path(self, ticket_id: int, filename: str) -> Optional[str]:
        """Get local attachment file path"""
        local_path = Path(f"../data_to_be_migrated/attachments/{ticket_id}/{filename}")
        if local_path.exists():
            return str(local_path)
        return None
    
    def process_ticket_attachments(self, issue_key: str, ticket_id: int, attachments: List[Dict]) -> int:
        """Process all attachments for a ticket"""
        uploaded_count = 0
        
        for attachment in attachments:
            filename = attachment.get('name', '')
            url = attachment.get('url', '')
            
            if not filename or not url:
                continue
            
            # Try local file first
            local_path = self.get_local_attachment_path(ticket_id, filename)
            if local_path:
                if self.upload_attachment_to_jira(issue_key, local_path):
                    uploaded_count += 1
                    print(f"Uploaded local attachment: {filename}")
                continue
            
            # Download from URL if local file not found
            downloaded_path = self.download_attachment(url, filename)
            if downloaded_path:
                if self.upload_attachment_to_jira(issue_key, downloaded_path):
                    uploaded_count += 1
                    print(f"Uploaded downloaded attachment: {filename}")
                
                # Clean up downloaded file
                try:
                    os.remove(downloaded_path)
                except:
                    pass
        
        return uploaded_count
    
    def process_conversation_attachments(self, issue_key: str, ticket_id: int, attachments: List[Dict]) -> int:
        """Process conversation attachments"""
        return self.process_ticket_attachments(issue_key, ticket_id, attachments)
    
    def cleanup(self):
        """Clean up temporary files"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except:
            pass
