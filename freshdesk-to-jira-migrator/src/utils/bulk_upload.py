"""
Bulk attachment upload utilities for JIRA.
Handles efficient upload of multiple attachments using bulk and parallel methods.
"""

import os
import requests
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


class BulkAttachmentUploader:
    """
    Handles bulk upload of attachments to JIRA.
    """
    
    def __init__(self, jira_config: Dict[str, Any]):
        """
        Initialize the bulk uploader.
        
        Args:
            jira_config: JIRA configuration dictionary
        """
        self.base_url = f"https://{jira_config['domain']}/rest/api/3"
        self.auth = (jira_config['email'], jira_config['api_token'])
        self.max_batch_size = 50  # Maximum files per batch
        self.max_batch_size_mb = 25  # Maximum batch size in MB
        
    def upload_attachments_bulk(self, issue_key: str, file_paths: List[str]) -> List[bool]:
        """
        Upload multiple attachments in a single request.
        
        Args:
            issue_key: JIRA issue key
            file_paths: List of file paths to upload
            
        Returns:
            List of boolean results indicating success/failure
        """
        if not file_paths:
            return []
        
        # Split files into batches based on size and count
        batches = self._create_batches(file_paths)
        results = []
        
        for batch in batches:
            batch_results = self._upload_batch(issue_key, batch)
            results.extend(batch_results)
        
        return results
    
    def upload_attachments_with_renaming(self, issue_key: str, attachment_data: List[Dict[str, Any]]) -> List[bool]:
        """
        Upload multiple attachments with renaming to attachmentId_nameofthefile format.
        
        Args:
            issue_key: JIRA issue key
            attachment_data: List of attachment data dictionaries with file_path, attachment_id, and original_name
            
        Returns:
            List of boolean results indicating success/failure
        """
        if not attachment_data:
            return []
        
        # Split attachments into batches based on size and count
        batches = self._create_attachment_batches(attachment_data)
        results = []
        
        for batch in batches:
            batch_results = self._upload_batch_with_renaming(issue_key, batch)
            results.extend(batch_results)
        
        return results
    
    def upload_attachments_parallel(self, issue_key: str, file_paths: List[str], max_workers: int = 5) -> List[bool]:
        """
        Upload attachments in parallel using multiple threads.
        
        Args:
            issue_key: JIRA issue key
            file_paths: List of file paths to upload
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of boolean results indicating success/failure
        """
        if not file_paths:
            return []
        
        results = [False] * len(file_paths)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit upload tasks
            future_to_index = {
                executor.submit(self._upload_single_file, issue_key, file_path): i
                for i, file_path in enumerate(file_paths)
            }
            
            # Collect results
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    print(f"Error uploading file {file_paths[index]}: {e}")
                    results[index] = False
        
        return results
    
    def _create_batches(self, file_paths: List[str]) -> List[List[str]]:
        """
        Create batches of files based on size and count limits.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            List of file path batches
        """
        batches = []
        current_batch = []
        current_batch_size = 0
        
        for file_path in file_paths:
            if not os.path.exists(file_path):
                print(f"Warning: File not found: {file_path}")
                continue
            
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Check if adding this file would exceed limits
            if (len(current_batch) >= self.max_batch_size or 
                current_batch_size + file_size_mb > self.max_batch_size_mb):
                
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_batch_size = 0
            
            current_batch.append(file_path)
            current_batch_size += file_size_mb
        
        # Add the last batch
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _create_attachment_batches(self, attachment_data: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Create batches of attachments based on size and count limits.
        
        Args:
            attachment_data: List of attachment data dictionaries
            
        Returns:
            List of attachment data batches
        """
        batches = []
        current_batch = []
        current_batch_size = 0
        
        for attachment in attachment_data:
            file_path = attachment['file_path']
            if not os.path.exists(file_path):
                print(f"Warning: File not found: {file_path}")
                continue
            
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Check if adding this file would exceed limits
            if (len(current_batch) >= self.max_batch_size or 
                current_batch_size + file_size_mb > self.max_batch_size_mb):
                
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_batch_size = 0
            
            current_batch.append(attachment)
            current_batch_size += file_size_mb
        
        # Add the last batch
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _upload_batch(self, issue_key: str, file_paths: List[str]) -> List[bool]:
        """
        Upload a batch of files in a single request.
        
        Args:
            issue_key: JIRA issue key
            file_paths: List of file paths in the batch
            
        Returns:
            List of boolean results
        """
        if not file_paths:
            return []
        
        url = f"{self.base_url}/issue/{issue_key}/attachments"
        
        try:
            # Prepare multipart form data
            files = []
            for file_path in file_paths:
                if os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    files.append(('file', (filename, open(file_path, 'rb'), 'application/octet-stream')))
            
            if not files:
                return [False] * len(file_paths)
            
            # Upload the batch
            response = requests.post(
                url,
                auth=self.auth,
                files=files,
                headers={'X-Atlassian-Token': 'no-check'}
            )
            
            # Close file handles
            for _, (_, file_obj, _) in files:
                file_obj.close()
            
            if response.status_code == 200:
                print(f"✅ Successfully uploaded batch of {len(files)} files")
                return [True] * len(files)
            else:
                print(f"❌ Failed to upload batch: {response.status_code} - {response.text}")
                return [False] * len(files)
                
        except Exception as e:
            print(f"❌ Error uploading batch: {e}")
            return [False] * len(file_paths)
    
    def _upload_batch_with_renaming(self, issue_key: str, attachment_batch: List[Dict[str, Any]]) -> List[bool]:
        """
        Upload a batch of files with renaming to attachmentId_nameofthefile format.
        
        Args:
            issue_key: JIRA issue key
            attachment_batch: List of attachment data dictionaries in the batch
            
        Returns:
            List of boolean results
        """
        if not attachment_batch:
            return []
        
        url = f"{self.base_url}/issue/{issue_key}/attachments"
        
        try:
            # Prepare multipart form data with renamed files
            files = []
            for attachment in attachment_batch:
                file_path = attachment['file_path']
                attachment_id = attachment['attachment_id']
                original_name = attachment['original_name']
                
                if os.path.exists(file_path):
                    # Create new filename: attachmentId_nameofthefile
                    new_filename = f"{attachment_id}_{original_name}"
                    files.append(('file', (new_filename, open(file_path, 'rb'), 'application/octet-stream')))
            
            if not files:
                return [False] * len(attachment_batch)
            
            # Upload the batch
            response = requests.post(
                url,
                auth=self.auth,
                files=files,
                headers={'X-Atlassian-Token': 'no-check'}
            )
            
            # Close file handles
            for _, (_, file_obj, _) in files:
                file_obj.close()
            
            if response.status_code == 200:
                print(f"✅ Successfully uploaded batch of {len(files)} files with renaming")
                return [True] * len(files)
            else:
                print(f"❌ Failed to upload batch: {response.status_code} - {response.text}")
                return [False] * len(files)
                
        except Exception as e:
            print(f"❌ Error uploading batch: {e}")
            return [False] * len(attachment_batch)
    
    def _upload_single_file(self, issue_key: str, file_path: str) -> bool:
        """
        Upload a single file.
        
        Args:
            issue_key: JIRA issue key
            file_path: Path to the file to upload
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(file_path):
            print(f"Warning: File not found: {file_path}")
            return False
        
        url = f"{self.base_url}/issue/{issue_key}/attachments"
        filename = os.path.basename(file_path)
        
        try:
            with open(file_path, 'rb') as f:
                response = requests.post(
                    url,
                    auth=self.auth,
                    files={'file': (filename, f, 'application/octet-stream')},
                    headers={'X-Atlassian-Token': 'no-check'}
                )
            
            if response.status_code == 200:
                print(f"✅ Successfully uploaded: {filename}")
                return True
            else:
                print(f"❌ Failed to upload {filename}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error uploading {filename}: {e}")
            return False
    
    def get_upload_stats(self, results: List[bool]) -> Dict[str, Any]:
        """
        Get statistics from upload results.
        
        Args:
            results: List of boolean upload results
            
        Returns:
            Statistics dictionary
        """
        total = len(results)
        successful = sum(results)
        failed = total - successful
        
        return {
            "total_files": total,
            "successful_uploads": successful,
            "failed_uploads": failed,
            "success_rate": successful / total if total > 0 else 0
        }
    
    def set_batch_limits(self, max_batch_size: int = 50, max_batch_size_mb: int = 25):
        """
        Set batch size limits.
        
        Args:
            max_batch_size: Maximum number of files per batch
            max_batch_size_mb: Maximum batch size in MB
        """
        self.max_batch_size = max_batch_size
        self.max_batch_size_mb = max_batch_size_mb
