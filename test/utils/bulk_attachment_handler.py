import os
import requests
from typing import List, Dict, Any
from config.jira_config import JiraConfig

class BulkAttachmentHandler:
    """Handle bulk attachment uploads using direct REST API calls"""
    
    def __init__(self):
        self.config = JiraConfig()
        self.base_url = f"https://{self.config.domain}/rest/api/3"
        self.auth = (self.config.email, self.config.api_token)
    
    def upload_attachments_bulk(self, issue_key: str, file_paths: List[str]) -> List[bool]:
        """
        Attempt to upload multiple attachments in a single request
        Returns list of success status for each file
        """
        if not file_paths:
            return []
        
        # Prepare multipart form data with multiple files
        files = []
        for file_path in file_paths:
            if os.path.exists(file_path):
                filename = os.path.basename(file_path)
                files.append(('file', (filename, open(file_path, 'rb'), 'application/octet-stream')))
        
        if not files:
            print("No valid files found to upload")
            return [False] * len(file_paths)
        
        try:
            # Make bulk upload request
            url = f"{self.base_url}/issue/{issue_key}/attachments"
            headers = {
                'X-Atlassian-Token': 'no-check',  # Required for file uploads
                'Accept': 'application/json'
            }
            
            print(f"Attempting bulk upload of {len(files)} attachments to {issue_key}...")
            response = requests.post(url, files=files, headers=headers, auth=self.auth)
            
            # Close all file handles
            for _, (_, file_handle, _) in files:
                file_handle.close()
            
            if response.status_code == 200:
                print(f"✅ Bulk upload successful! Uploaded {len(files)} attachments")
                return [True] * len(files)
            else:
                print(f"❌ Bulk upload failed with status {response.status_code}: {response.text}")
                return [False] * len(files)
                
        except Exception as e:
            print(f"❌ Bulk upload error: {e}")
            # Close any open file handles
            for _, (_, file_handle, _) in files:
                try:
                    file_handle.close()
                except:
                    pass
            return [False] * len(files)
    
    def upload_attachments_parallel(self, issue_key: str, file_paths: List[str]) -> List[bool]:
        """
        Upload multiple attachments in parallel using concurrent requests
        Returns list of success status for each file
        """
        import concurrent.futures
        from functools import partial
        
        def upload_single_attachment(file_path: str) -> bool:
            """Upload a single attachment"""
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                return False
            
            try:
                filename = os.path.basename(file_path)
                url = f"{self.base_url}/issue/{issue_key}/attachments"
                headers = {
                    'X-Atlassian-Token': 'no-check',
                    'Accept': 'application/json'
                }
                
                with open(file_path, 'rb') as f:
                    files = {'file': (filename, f, 'application/octet-stream')}
                    response = requests.post(url, files=files, headers=headers, auth=self.auth)
                
                if response.status_code == 200:
                    print(f"✅ Uploaded: {filename}")
                    return True
                else:
                    print(f"❌ Failed to upload {filename}: {response.status_code}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error uploading {file_path}: {e}")
                return False
        
        print(f"Starting parallel upload of {len(file_paths)} attachments...")
        
        # Use ThreadPoolExecutor for parallel uploads
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(upload_single_attachment, file_paths))
        
        success_count = sum(results)
        print(f"✅ Parallel upload completed: {success_count}/{len(file_paths)} successful")
        return results
