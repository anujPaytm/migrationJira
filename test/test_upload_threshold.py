#!/usr/bin/env python3
"""
Test script to determine the threshold for bulk attachment uploads
"""

import sys
import os
import time
sys.path.append('.')

from utils.bulk_attachment_handler import BulkAttachmentHandler
from utils.data_loader import DataLoader
from utils.user_mapper import UserMapper
from utils.ticket_converter import TicketConverter
from config.jira_config import JiraConfig
from jira import JIRA

def create_test_files(base_path: str, num_files: int, file_size_kb: int = 10) -> list:
    """Create test files of specified size"""
    file_paths = []
    os.makedirs(base_path, exist_ok=True)
    
    for i in range(num_files):
        filename = f"test_file_{i+1}.txt"
        file_path = os.path.join(base_path, filename)
        
        # Create file with specified size
        content = "A" * (file_size_kb * 1024)  # Convert KB to bytes
        with open(file_path, 'w') as f:
            f.write(content)
        
        file_paths.append(file_path)
        print(f"Created test file: {filename} ({file_size_kb}KB)")
    
    return file_paths

def test_upload_threshold():
    """Test different batch sizes to find upload threshold"""
    print("Testing Bulk Upload Threshold")
    print("=" * 60)
    
    # Initialize handlers
    bulk_handler = BulkAttachmentHandler()
    config = JiraConfig()
    jira = JIRA(options=config.get_jira_options(), basic_auth=config.get_auth())
    
    # Load test data for creating issue
    data_loader = DataLoader()
    users_data = data_loader.load_users()
    user_mapper = UserMapper(users_data)
    
    # Get ticket 55 data for creating test issue
    ticket = data_loader.load_ticket_details(55)
    converter = TicketConverter(user_mapper)
    jira_issue = converter.convert_to_jira_issue(ticket, [], [], [])
    
    # Create test issue
    print("Creating test issue...")
    issue = jira.create_issue(fields=jira_issue["fields"])
    print(f"✅ Created test issue: {issue.key}")
    
    # Test with very large files to find the real MB limit
    batch_sizes = [1, 2, 3, 4, 5]
    file_size_kb = 25600  # 25MB test files (25 * 1024 KB)
    test_dir = "test_upload_files"
    
    results = {}
    
    try:
        for batch_size in batch_sizes:
            print(f"\n{'='*20} Testing Batch Size: {batch_size} {'='*20}")
            
            # Create test files
            file_paths = create_test_files(test_dir, batch_size, file_size_kb)
            total_size_mb = (batch_size * file_size_kb) / 1024
            
            print(f"Total batch size: {total_size_mb:.2f}MB")
            
            try:
                # Attempt bulk upload
                start_time = time.time()
                results_list = bulk_handler.upload_attachments_bulk(issue.key, file_paths)
                end_time = time.time()
                
                success_count = sum(results_list)
                duration = end_time - start_time
                
                if success_count == batch_size:
                    print(f"✅ SUCCESS: {success_count}/{batch_size} files uploaded in {duration:.2f}s")
                    results[batch_size] = {
                        'status': 'SUCCESS',
                        'success_count': success_count,
                        'duration': duration,
                        'total_size_mb': total_size_mb
                    }
                else:
                    print(f"❌ PARTIAL: {success_count}/{batch_size} files uploaded")
                    results[batch_size] = {
                        'status': 'PARTIAL',
                        'success_count': success_count,
                        'duration': duration,
                        'total_size_mb': total_size_mb
                    }
                    
            except Exception as e:
                print(f"❌ FAILED: {str(e)}")
                results[batch_size] = {
                    'status': 'FAILED',
                    'error': str(e),
                    'total_size_mb': total_size_mb
                }
                # Stop testing if we hit a hard failure
                break
            
            # Clean up test files
            for file_path in file_paths:
                try:
                    os.remove(file_path)
                except:
                    pass
            
            # Small delay between tests
            time.sleep(1)
    
    finally:
        # Clean up test directory
        try:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)
        except:
            pass
        
        # Delete test issue
        try:
            issue.delete()
            print(f"\n✅ Cleaned up test issue: {issue.key}")
        except:
            print(f"\n⚠️  Could not delete test issue: {issue.key}")
    
    # Print results summary
    print(f"\n{'='*60}")
    print("THRESHOLD TEST RESULTS")
    print(f"{'='*60}")
    
    max_successful = 0
    for batch_size, result in results.items():
        status = result['status']
        if status == 'SUCCESS':
            max_successful = batch_size
            print(f"✅ {batch_size:2d} files: SUCCESS ({result['duration']:.2f}s, {result['total_size_mb']:.2f}MB)")
        elif status == 'PARTIAL':
            print(f"⚠️  {batch_size:2d} files: PARTIAL ({result['success_count']}/{batch_size})")
        else:
            print(f"❌ {batch_size:2d} files: FAILED - {result.get('error', 'Unknown error')}")
    
    print(f"\n🎯 RECOMMENDED THRESHOLD: {max_successful} files")
    print(f"📊 Total size limit: {results[max_successful]['total_size_mb']:.2f}MB")
    
    if max_successful > 0:
        print(f"\n💡 For production use, recommend using {max_successful - 2} files per batch for safety margin")

if __name__ == "__main__":
    test_upload_threshold()
