# Atomic Operations for Freshdesk to JIRA Migration

## Overview

The migration system now implements **atomic operations** to ensure data consistency and prevent orphaned JIRA issues. This means that each ticket migration is either completely successful (ticket created + attachments uploaded + tracker updated) or completely fails (no JIRA issue created, or cleanup if partial failure).

## Problem Solved

Previously, the migration could create JIRA issues but fail to:
- Upload attachments
- Update the migration tracker
- Handle partial failures properly

This led to **286 orphaned issues** in your previous migration - issues that existed in JIRA but weren't tracked in the migration tracker.

## How Atomic Operations Work

### 1. **Issue Creation with Cleanup Tracking**
```python
# Create JIRA issue
created_issue = self._create_jira_issue_single_attempt(ticket_id, jira_issue)

# Mark for potential cleanup
self._mark_issue_for_cleanup(ticket_id, created_issue.key)
```

### 2. **Attachment Upload with Rollback**
```python
try:
    self._upload_attachments(created_issue.key, ticket_data)
except Exception as attachment_error:
    # Clean up the issue since attachments failed
    self._cleanup_orphaned_issue(created_issue.key, ticket_id)
    raise attachment_error
```

### 3. **Success Confirmation**
```python
# Update tracker with success
self.tracker.update_ticket_status(ticket_id, "success", jira_id=created_issue.key)

# Remove cleanup mark since we succeeded
self._remove_cleanup_mark(ticket_id)
```

### 4. **Failure Cleanup**
```python
# Clean up any created issue on failure
if created_issue:
    self._cleanup_orphaned_issue(created_issue.key, ticket_id)
    created_issue = None
```

## Key Features

### 🔒 **Thread-Safe Operations**
- Uses `threading.Lock()` for atomic operations
- Prevents race conditions in parallel processing
- Safe cleanup even with multiple workers

### 🧹 **Automatic Cleanup**
- **Pending Issues Tracking**: Issues are marked for cleanup immediately after creation
- **Failure Detection**: Any failure triggers automatic cleanup
- **Interruption Handling**: Keyboard interrupts trigger cleanup of pending issues

### 📊 **Enhanced Statistics**
- Tracks `orphaned_issues_cleaned` in migration statistics
- Provides visibility into cleanup operations

### 🔄 **Retry with Cleanup**
- 3-retry mechanism with exponential backoff
- Each retry attempt cleans up previous failures
- Only final success removes cleanup marks

## Usage

### Normal Migration (Atomic Operations Enabled by Default)
```bash
# Migration automatically uses atomic operations
python3 scripts/migrate_tickets.py --all --workers 20
```

### Interruption Handling
```bash
# If you interrupt the migration (Ctrl+C), cleanup happens automatically
python3 scripts/migrate_tickets.py --all --workers 20
# Press Ctrl+C during migration
# System automatically cleans up pending issues
```

## Cleanup Utility

### Analyze Orphaned Issues
```bash
# Analyze orphaned issues from previous migrations
python3 scripts/cleanup_orphaned_issues.py --analyze-only
```

### Dry Run Cleanup
```bash
# See what would be deleted without actually deleting
python3 scripts/cleanup_orphaned_issues.py --delete-all --dry-run
```

### Clean Up Orphaned Issues
```bash
# Delete all orphaned issues (use with caution!)
python3 scripts/cleanup_orphaned_issues.py --delete-all
```

## Migration Flow

```
1. Load ticket data
   ↓
2. Convert to JIRA format
   ↓
3. Create JIRA issue
   ↓
4. Mark for cleanup (atomic)
   ↓
5. Upload attachments
   ↓
6. Update tracker
   ↓
7. Remove cleanup mark (atomic)
   ↓
8. SUCCESS ✅
```

**If any step fails:**
```
❌ FAILURE DETECTED
   ↓
🧹 Cleanup orphaned issue
   ↓
📝 Update tracker with failure
   ↓
❌ FAILED ✅ (clean state)
```

## Benefits

### ✅ **Data Consistency**
- No orphaned JIRA issues
- Perfect 1:1 mapping between tracker and JIRA
- Clean failure states

### ✅ **Reliability**
- Handles network failures gracefully
- Manages API rate limits
- Recovers from interruptions

### ✅ **Visibility**
- Clear success/failure tracking
- Detailed cleanup statistics
- Audit trail for all operations

### ✅ **Safety**
- Dry run capabilities
- Confirmation prompts for destructive operations
- Comprehensive error handling

## Migration Statistics

The system now tracks:
- `total_tickets`: Total tickets processed
- `successful_migrations`: Successfully migrated tickets
- `failed_migrations`: Failed migrations
- `orphaned_issues_cleaned`: Issues cleaned up during migration
- `attachment_success_rate`: Percentage of successful attachment uploads

## Best Practices

### 1. **Always Use Atomic Operations**
- Enabled by default in new migrations
- Ensures data consistency

### 2. **Monitor Cleanup Statistics**
- Check `orphaned_issues_cleaned` in migration logs
- Investigate if cleanup count is high

### 3. **Use Dry Runs**
- Test migrations with `--dry-run` first
- Verify atomic behavior before live migration

### 4. **Handle Interruptions Gracefully**
- Use Ctrl+C to stop migrations safely
- System will clean up pending issues automatically

### 5. **Regular Cleanup**
- Run orphaned issue analysis periodically
- Clean up any issues from previous migrations

## Troubleshooting

### High Cleanup Count
If you see many `orphaned_issues_cleaned`:
1. Check network connectivity
2. Verify JIRA API rate limits
3. Reduce parallel workers
4. Check attachment file availability

### Cleanup Failures
If cleanup operations fail:
1. Check JIRA permissions
2. Verify issue still exists
3. Check API rate limits
4. Use manual cleanup utility

### Tracker Inconsistencies
If tracker shows different counts than JIRA:
1. Run orphaned issue analysis
2. Clean up orphaned issues
3. Verify migration completion

## Example Output

```
🔄 Starting migration for ticket 12345
🚀 Creating JIRA issue for ticket 12345 (attempt 1/3)...
✅ Successfully created JIRA issue: FTJM-12345
📎 Uploading 3 ticket attachments...
📎 Uploaded 3/3 ticket attachments
✅ Successfully migrated ticket 12345 to FTJM-12345

=== Migration Summary ===
Total tickets: 1000
Successful migrations: 998
Failed migrations: 2
Orphaned issues cleaned: 0
Success rate: 99.8%
```

This ensures that your migration maintains perfect data consistency and prevents the orphaned issue problem you experienced before.
