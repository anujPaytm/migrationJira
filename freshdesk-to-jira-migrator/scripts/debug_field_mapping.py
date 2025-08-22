#!/usr/bin/env python3
"""
Debug field mapping to see what's happening
"""

import sys
import os
import json

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add project root and src to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(project_root))
sys.path.insert(0, os.path.join(project_root, "src"))

from core.field_mapper import FieldMapper
from config.mapper_functions import apply_mapper_function

def debug_field_mapping():
    """Debug field mapping for ticket 55"""
    
    # Load ticket 55 data
    with open('../sample_data/ticket_details/ticket_55_details.json', 'r') as f:
        ticket_data = json.load(f)
    
    # Initialize field mapper
    field_mapper = FieldMapper()
    
    print("=== DEBUGGING FIELD MAPPING ===")
    print(f"Ticket data keys: {list(ticket_data.keys())}")
    print()
    
    # Test specific fields that should be mapped
    test_fields = [
        'fr_escalated',      # should be False
        'spam',              # should be False  
        'is_escalated',      # should be False
        'nr_escalated',      # should be False
        'email_config_id',   # should be 1060000051131
        'product_id',        # should be 1060000043624
        'ticket_id',         # should be 55
        'sentiment_score',   # should be 64
        'initial_sentiment_score',  # should be 64
        'custom_fields'      # should be formatted string
    ]
    
    for field_name in test_fields:
        if field_name in ticket_data:
            field_value = ticket_data[field_name]
            print(f"Field: {field_name}")
            print(f"  Original value: {field_value} (type: {type(field_value)})")
            
            # Get mapping
            mapping = field_mapper.get_field_mapping(field_name, "ticket_fields")
            if mapping:
                print(f"  Mapping found: {mapping}")
                jira_field = mapping.get('jira_field')
                mapper_function = mapping.get('mapper_function')
                
                if mapper_function:
                    print(f"  Mapper function: {mapper_function}")
                    mapped_value = apply_mapper_function(mapper_function, field_value)
                    print(f"  Mapped value: {mapped_value} (type: {type(mapped_value)})")
                else:
                    print(f"  No mapper function, using original value")
                    mapped_value = field_value
                
                print(f"  JIRA field: {jira_field}")
                print(f"  Final value: {mapped_value}")
            else:
                print(f"  No mapping found")
            print()
        else:
            print(f"Field: {field_name} - NOT FOUND IN TICKET DATA")
            print()

if __name__ == "__main__":
    debug_field_mapping()
