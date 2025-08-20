# Freshdesk to JIRA Migration Tool

A comprehensive Python tool for migrating Freshdesk tickets to JIRA with full data preservation including attachments, conversations, and custom fields.

## 🚀 Features

- **Complete Data Migration**: Migrate tickets, conversations, attachments, and custom fields
- **Smart Field Mapping**: Uses JIRA system fields where possible, custom fields where needed
- **User Mapping**: Maps Freshdesk users to JIRA users
- **Attachment Handling**: Downloads and uploads attachments to JIRA
- **Custom Field Support**: Maps Freshdesk data to JIRA custom fields
- **Dry Run Mode**: Test migrations without creating actual JIRA issues
- **Batch Processing**: Process multiple tickets efficiently
- **Error Handling**: Robust error handling and logging

## 📋 Prerequisites

- Python 3.7+
- JIRA instance with API access
- Freshdesk data export (JSON format)
- Required Python packages (see requirements.txt)

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/anujPaytm/migrationJira.git
   cd migrationJira
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   cp env_template.txt .env
   # Edit .env with your JIRA credentials
   ```

## ⚙️ Configuration

### Environment Variables (.env)

```env
# JIRA Configuration
JIRA_API_TOKEN=your_jira_api_token
JIRA_PROJECT_KEY=your_project_key
JIRA_DOMAIN=your_domain.atlassian.net
JIRA_EMAIL=your_email@domain.com

# Migration Configuration
DRY_RUN=true
BATCH_SIZE=10
MAX_RETRIES=3
RETRY_DELAY=5
```

### Data Structure

The tool expects Freshdesk data in the following structure:

```
data_to_be_migrated/
├── ticket_details/          # Ticket information
├── conversations/           # Ticket conversations
├── ticket_attachments/      # Ticket-level attachments
├── conversation_attachments/ # Conversation-level attachments
├── user_details/           # User information (agents, contacts)
└── attachments/            # Physical attachment files
```

## 🚀 Usage

### Basic Migration

```bash
# Migrate a single ticket
python scripts/migrate_tickets.py --ticket-id 55

# Migrate multiple tickets
python scripts/migrate_tickets.py --ticket-ids 55,94,7885

# Dry run (test without creating issues)
DRY_RUN=true python scripts/migrate_tickets.py --ticket-id 55
```

### Testing

```bash
# Run test suite
python scripts/test_migration.py

# Test configuration
python setup.py
```

### Custom Field Mapping

```bash
# Fetch JIRA custom fields
python scripts/fetch_custom_fields.py
```

## 📊 Field Mapping

### System Fields (Direct JIRA Mapping)
- `subject` → `summary`
- `description` → `description`
- `priority` → `priority`
- `due_by` → `duedate`

### Custom Fields (FD_ prefix)
- `cc_emails` → `FD_cc_emails`
- `to_emails` → `FD_to_emails`
- `requester_id` → `FD_requester_id`
- `responder_id` → `FD_responder_id`
- And many more...

## 📁 Project Structure

```
├── config/
│   └── jira_config.py          # JIRA configuration
├── utils/
│   ├── data_loader.py          # Data loading utilities
│   ├── user_mapper.py          # User mapping logic
│   ├── ticket_converter.py     # Ticket conversion
│   └── attachment_handler.py   # Attachment handling
├── scripts/
│   ├── migrate_tickets.py      # Main migration script
│   ├── test_migration.py       # Test suite
│   └── fetch_custom_fields.py  # Custom field fetcher
├── sample_data/                # Sample data for testing
├── requirements.txt            # Python dependencies
├── env_template.txt           # Environment template
└── README.md                  # This file
```

## 🔧 Customization

### Adding New Field Mappings

1. Update `field_mapping.json` with new mappings
2. Create corresponding custom fields in JIRA
3. Update `ticket_converter.py` to use new fields

### Custom Field Types

The tool supports various JIRA custom field types:
- Text fields
- Number fields
- Date fields
- Boolean fields
- Multi-select fields

## 🐛 Troubleshooting

### Common Issues

1. **403 Forbidden**: Check JIRA permissions and API token
2. **404 Not Found**: Verify project key and issue type
3. **Attachment Upload Failures**: Check file permissions and URLs
4. **User Mapping Issues**: Verify user data in `user_details/`

### Debug Mode

```bash
# Enable debug logging
DEBUG=true python scripts/migrate_tickets.py --ticket-id 55
```

## 📝 Sample Data

The repository includes sample data for testing:
- `sample_data/ticket_details/ticket_55_details.json`
- `sample_data/conversations/ticket_55_conversations.json`
- `sample_data/ticket_attachments/ticket_55_attachments.json`
- `sample_data/user_details/` (agents and contacts)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the test suite
3. Create an issue on GitHub

## 🔗 Links

- [JIRA REST API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
- [Freshdesk API Documentation](https://developers.freshdesk.com/api/)
- [Python JIRA Library](https://jira.readthedocs.io/)

---

**Note**: This tool is designed for migrating Freshdesk data to JIRA. Always test with dry-run mode before performing actual migrations.
