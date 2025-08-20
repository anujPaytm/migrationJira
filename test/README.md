# Freshdesk to JIRA Migration Tool

This tool migrates Freshdesk tickets to JIRA, including ticket details, conversations, attachments, and user mapping.

## Features

- **Complete Data Migration**: Migrates tickets, conversations, and attachments
- **User Mapping**: Maps Freshdesk users to JIRA users
- **Metabase-style Description**: Formats ticket data in a structured, readable format
- **Batch Processing**: Processes tickets in configurable batches
- **Error Handling**: Robust error handling with retry mechanisms
- **Dry Run Mode**: Test migration without creating actual JIRA issues
- **Progress Tracking**: Comprehensive logging and reporting

## Setup

### 1. Install Dependencies

```bash
cd test
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the environment template and update with your JIRA credentials:

```bash
cp env_template.txt .env
```

Edit `.env` file with your JIRA configuration:

```env
# JIRA Configuration
JIRA_API_TOKEN=your_api_token_here
JIRA_PROJECT_KEY=FTJM
JIRA_DOMAIN=paytm-test.atlassian.net
JIRA_EMAIL=your-email@paytm.com

# Migration Configuration
DRY_RUN=true
BATCH_SIZE=10
MAX_RETRIES=3
RETRY_DELAY=5
```

### 3. Data Structure

Ensure your Freshdesk data is organized as follows:

```
data_to_be_migrated/
├── ticket_details/
│   ├── ticket_52_details.json
│   └── ...
├── conversations/
│   ├── ticket_52_conversations.json
│   └── ...
├── ticket_attachments/
│   ├── ticket_52_attachments.json
│   └── ...
├── conversation_attachments/
│   ├── ticket_52_conversation_attachments.json
│   └── ...
├── user_details/
│   ├── all_agents.json
│   ├── all_contacts.json
│   └── user_summary.json
└── attachments/
    ├── 52/
    │   ├── file1.pdf
    │   └── file2.jpg
    └── ...
```

## Usage

### Test the Setup

First, run the test suite to ensure everything is configured correctly:

```bash
python scripts/test_migration.py
```

### Dry Run (Recommended First Step)

Test the migration without creating actual JIRA issues:

```bash
python scripts/migrate_tickets.py --dry-run --limit 5
```

### Migrate Specific Ticket

```bash
python scripts/migrate_tickets.py --ticket-id 52
```

### Migrate All Tickets

```bash
python scripts/migrate_tickets.py
```

### Migrate with Limit

```bash
python scripts/migrate_tickets.py --limit 100
```

## Configuration Options

### Environment Variables

- `JIRA_API_TOKEN`: Your JIRA API token
- `JIRA_PROJECT_KEY`: Target JIRA project key
- `JIRA_DOMAIN`: Your JIRA domain
- `JIRA_EMAIL`: Your JIRA email address
- `DRY_RUN`: Set to `true` for testing, `false` for actual migration
- `BATCH_SIZE`: Number of tickets to process in each batch
- `MAX_RETRIES`: Maximum number of retry attempts
- `RETRY_DELAY`: Delay between retries in seconds

## Migration Process

### 1. Data Loading
- Loads ticket details, conversations, and attachments from JSON files
- Loads user data (agents and contacts) for mapping

### 2. User Mapping
- Maps Freshdesk requester IDs to contact information
- Maps Freshdesk responder IDs to agent information
- Resolves conversation authors

### 3. Ticket Conversion
- Converts Freshdesk ticket format to JIRA issue format
- Creates metabase-style description with metadata and comments
- Maps priorities and statuses

### 4. JIRA Upload
- Creates JIRA issues with converted data
- Uploads attachments (local files preferred, URLs as fallback)
- Handles rate limiting and retries

## Output Format

### JIRA Issue Description

The tool creates a structured description in this format:

```
— Freshdesk Metadata —
id: 52
created_at: 2024-05-02T07:42:31Z
updated_at: 2024-07-29T17:35:51Z
source: Email
product_id: 1060000043624
fr_due_by: 2024-05-06T07:42:31Z
fr_escalated: False
is_escalated: False
spam: False
email_config_id: 1060000054966
priority: 1
status: 5
...

— Description —
[Original ticket description]

— Comments —
**Neetu kurichh** (neetu.kurichh@paytm.com) - 2024-05-03 05:47:31
Dear Partner,
Please get in touch with your business spoc.
Regards
Neetu Kurichh
Vendor Helpdesk
---
```

### Migration Report

After migration, a report is generated showing:
- Total tickets processed
- Success/failure counts
- Success rate
- List of migrated tickets with JIRA keys
- List of failed migrations with error details

## Error Handling

The tool includes comprehensive error handling:

- **Network Errors**: Automatic retries with exponential backoff
- **Rate Limiting**: Respects JIRA API rate limits
- **Invalid Data**: Skips invalid tickets and continues processing
- **Attachment Failures**: Continues migration even if attachments fail
- **User Mapping**: Handles missing user data gracefully

## Troubleshooting

### Common Issues

1. **JIRA Connection Failed**
   - Verify API token and domain
   - Check network connectivity
   - Ensure JIRA project exists

2. **Data Loading Errors**
   - Verify file paths and structure
   - Check JSON file format
   - Ensure required files exist

3. **User Mapping Issues**
   - Verify user data files
   - Check user ID consistency
   - Ensure email addresses are valid

4. **Attachment Upload Failures**
   - Check file permissions
   - Verify file paths
   - Ensure JIRA has sufficient storage

### Debug Mode

For detailed debugging, you can modify the logging level in the scripts or add print statements to track the migration process.

## Safety Features

- **Dry Run Mode**: Test without creating actual issues
- **Batch Processing**: Process in small batches to avoid overwhelming JIRA
- **Backup**: Original data remains unchanged
- **Rollback**: Can delete created issues if needed
- **Validation**: Validates data before upload

## Support

For issues or questions:
1. Check the test output for configuration issues
2. Review the migration report for specific errors
3. Verify JIRA permissions and project access
4. Check network connectivity and API limits
