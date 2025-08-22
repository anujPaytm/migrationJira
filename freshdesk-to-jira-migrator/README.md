# Freshdesk to JIRA Migrator

A modular, configurable migration tool to transfer tickets from Freshdesk to JIRA with flexible field mapping and bulk attachment handling.

## 🚀 Features

- **Configurable Field Mapping**: JSON-based mapping system for Freshdesk to JIRA field conversion
- **Flexible Field Types**: Support for both JIRA system fields and custom fields
- **Mapper Functions**: Custom transformation functions for field value conversion
- **Bulk Attachment Upload**: Optimized attachment handling with configurable batch sizes
- **Modular Architecture**: Clean separation of concerns with dedicated modules
- **Fallback Strategy**: Unmapped fields automatically added to description
- **Dry Run Mode**: Test migrations without creating actual JIRA issues

## 📁 Project Structure

```
freshdesk-to-jira-migrator/
├── config/
│   ├── field_mapping.json          # Main field mapping configuration
│   ├── jira_custom_fields.json     # JIRA custom field definitions
│   └── mapper_functions.py         # Custom field transformation functions
├── src/
│   ├── core/
│   │   ├── data_loader.py          # Data loading from Freshdesk exports
│   │   ├── field_mapper.py         # Field mapping logic
│   │   └── ticket_converter.py     # Ticket conversion to JIRA format
│   └── utils/
│       └── bulk_upload.py          # Bulk attachment upload
├── scripts/
│   └── migrate_tickets.py          # Main migration script
├── tests/
│   └── test_setup.py               # Setup verification tests
├── requirements.txt
├── env.example
└── README.md
```

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd freshdesk-to-jira-migrator
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   ```bash
   cp env.example .env
   # Edit .env with your JIRA credentials
   ```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# JIRA Configuration
JIRA_DOMAIN=your-domain.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your_jira_api_token_here
JIRA_PROJECT_KEY=FTJM

# Migration Configuration
DATA_DIRECTORY=../data_to_be_migrated
MIGRATE_ALL=false
TICKET_IDS="55,1001,1004"
DRY_RUN=true
MIGRATION_LIMIT=0
PARALLEL_WORKERS=8
SEQUENTIAL_MODE=false
LOG_FILE=""
JIRA_ISSUE_TYPE="Task"
```

### Configuration Options

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MIGRATE_ALL` | Migrate all available tickets | `false` | `true` |
| `TICKET_IDS` | Comma-separated list of specific ticket IDs | `""` | `"55,1001,1004"` |
| `DRY_RUN` | Perform dry run without creating JIRA issues | `false` | `true` |
| `MIGRATION_LIMIT` | Maximum tickets to migrate (0 = no limit) | `0` | `100` |
| `PARALLEL_WORKERS` | Number of parallel workers | `8` | `4` |
| `SEQUENTIAL_MODE` | Use sequential processing | `false` | `true` |
| `LOG_FILE` | Path to log file (empty = console only) | `""` | `"migration.log"` |
| `DATA_DIRECTORY` | Path to Freshdesk data directory | `../data_to_be_migrated` | `./my_data` |

### Usage Modes

**1. Environment-Based Configuration (Recommended)**
```bash
# Configure .env file and run without arguments
python3 scripts/migrate_tickets.py
```

**2. Command-Line Arguments (Backward Compatible)**
```bash
# Specific tickets with dry run
python3 scripts/migrate_tickets.py --ticket-ids 55 1001 1004 --dry-run

# Migrate all tickets
python3 scripts/migrate_tickets.py --all --limit 100

# Sequential processing
python3 scripts/migrate_tickets.py --ticket-ids 55 --sequential
```

### Field Mapping

The `config/field_mapping.json` contains mappings with the following structure:

```json
{
  "ticket_fields": {
    "field_name": {
      "jira_field": "field_id_or_name",
      "field_type": "system|custom",
      "mapper_function": "function_name|null"
    }
  }
}
```

### Mapper Functions

Custom transformation functions in `config/mapper_functions.py` handle field value conversions:

- **Priority mapping**: `1 → Low`, `2 → Medium`, `3 → High`, `4 → Urgent`
- **Status mapping**: Convert Freshdesk status codes to readable names
- **Email extraction**: Extract emails from various formats
- **Date formatting**: Convert ISO dates to JIRA format
- **List joining**: Convert arrays to comma-separated strings

## 📊 Field Mapping Strategy

1. **Mapped Fields**: If a field exists in mapping, it's sent to the corresponding JIRA field
2. **Unmapped Fields**: Automatically added to the description in a structured format
3. **Mapper Functions**: Applied to transform field values before sending to JIRA

## 🚀 Usage

### Basic Migration

1. **Test the setup**:
   ```bash
   python tests/test_setup.py
   ```

2. **Dry run migration** (test without creating issues):
   ```bash
   python scripts/migrate_tickets.py --ticket-ids 55 56 57 --dry-run
   ```

3. **Migrate specific tickets**:
   ```bash
   python scripts/migrate_tickets.py --ticket-ids 55 56 57
   ```

4. **Migrate all tickets**:
   ```bash
   python scripts/migrate_tickets.py --all
   ```

5. **Migrate with limit**:
   ```bash
   python scripts/migrate_tickets.py --all --limit 10
   ```

### Advanced Options

- `--data-dir`: Specify custom data directory path
- `--limit`: Limit number of tickets to migrate
- `--dry-run`: Test migration without creating JIRA issues

## 📋 Data Requirements

The tool expects Freshdesk data in the following structure:

```
data_to_be_migrated/
├── ticket_details/
│   ├── 55.json
│   ├── 56.json
│   └── ...
├── conversations/
│   ├── 55.json
│   ├── 56.json
│   └── ...
├── ticket_attachments/
│   ├── 55.json
│   ├── 56.json
│   └── ...
├── conversation_attachments/
│   ├── 55.json
│   ├── 56.json
│   └── ...
├── user_details/
│   ├── 1060011175358.json
│   └── ...
└── attachments/
    ├── 55/
    │   ├── file1.pdf
    │   └── file2.jpg
    └── 56/
        └── file3.pdf
```

## 🔧 Customization

### Adding New Field Mappings

1. **Edit `config/field_mapping.json`**:
   ```json
   {
     "ticket_fields": {
       "new_field": {
         "jira_field": "FD_new_field",
         "field_type": "custom",
         "mapper_function": "custom_mapper"
       }
     }
   }
   ```

2. **Add mapper function in `config/mapper_functions.py`**:
   ```python
   def custom_mapper(value):
       # Your transformation logic
       return transformed_value
   ```

### Configuring Custom Fields

Edit `config/jira_custom_fields.json` to define JIRA custom field mappings:

```json
{
  "custom_fields": {
    "FD_new_field": {
      "id": "customfield_10058",
      "name": "New Field",
      "type": "text",
      "description": "Description of the field"
    }
  }
}
```

## 📈 Performance

### Attachment Upload Optimization

- **Bulk Upload**: Up to 50 files per batch
- **Size Limits**: Maximum 25MB per batch
- **Parallel Processing**: Configurable thread count for parallel uploads

### Batch Processing

- **Memory Efficient**: Processes tickets one at a time
- **Error Handling**: Continues migration even if individual tickets fail
- **Progress Tracking**: Real-time progress updates

## 🐛 Troubleshooting

### Common Issues

1. **JIRA Connection Failed**:
   - Verify domain, email, and API token
   - Check network connectivity
   - Ensure API token has appropriate permissions

2. **Field Mapping Errors**:
   - Verify field mapping JSON syntax
   - Check that custom fields exist in JIRA
   - Ensure mapper functions are properly defined

3. **Attachment Upload Failures**:
   - Check file paths and permissions
   - Verify file sizes are within limits
   - Ensure JIRA has attachment upload permissions

### Debug Mode

Enable verbose logging by modifying the migration script or adding debug prints to mapper functions.

## 📝 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the configuration examples
3. Run the test setup script
4. Create an issue with detailed error information


