#!/bin/bash

# Shell script for continuous JIRA ticket deletion in batches
# Automatically confirms deletion and runs until all tickets are removed

echo "🚀 Starting continuous JIRA ticket deletion..."
echo "🎯 This will delete ALL tickets after FTJM-64 in batches of 100"
echo "🔧 Using 20 parallel workers per batch"
echo ""

# Configuration
AFTER_KEY="FTJM-64"
BATCH_SIZE=100
WORKERS=20
MAX_ITERATIONS=200  # Safety limit to prevent infinite loops

echo "⚠️  WARNING: This will delete ALL JIRA tickets after ${AFTER_KEY}!"
echo "📊 Batch size: ${BATCH_SIZE} tickets"
echo "🔧 Workers: ${WORKERS} parallel deletions"
echo "🔄 Max iterations: ${MAX_ITERATIONS}"
echo ""

read -p "Are you absolutely sure you want to continue? (type 'DELETE' to confirm): " confirmation

if [ "$confirmation" != "DELETE" ]; then
    echo "❌ Deletion cancelled. Exiting."
    exit 1
fi

echo ""
echo "🔥 Starting deletion process..."
echo "================================"

iteration=1

while [ $iteration -le $MAX_ITERATIONS ]; do
    echo ""
    echo "🔄 Iteration $iteration/$MAX_ITERATIONS"
    echo "⏰ $(date)"
    
    # Run the deletion script with auto-confirm
    python3 delete_jira_tickets.py \
        --after-key "$AFTER_KEY" \
        --batch-size "$BATCH_SIZE" \
        --workers "$WORKERS" \
        --auto-confirm
    
    exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        echo "❌ Deletion script failed with exit code $exit_code"
        echo "🔄 Waiting 10 seconds before retry..."
        sleep 10
    else
        echo "✅ Iteration $iteration completed successfully"
        echo "⏳ Waiting 5 seconds before next iteration..."
        sleep 5
    fi
    
    # Check if there are still tickets to delete
    echo "🔍 Checking if more tickets exist..."
    remaining_count=$(python3 -c "
import os
from jira import JIRA
from dotenv import load_dotenv

load_dotenv()

try:
    jira = JIRA(
        server=f'https://{os.getenv(\"JIRA_DOMAIN\")}',
        basic_auth=(os.getenv('JIRA_EMAIL'), os.getenv('JIRA_API_TOKEN'))
    )
    
    jql = f'project = FTJM AND key > $AFTER_KEY'
    issues = jira.search_issues(jql, maxResults=1, fields='key')
    print(len(issues))
except:
    print('1')  # Assume there are tickets if we can't check
")
    
    if [ "$remaining_count" = "0" ]; then
        echo ""
        echo "🎉 SUCCESS: No more tickets found after $AFTER_KEY"
        echo "✅ All tickets have been deleted!"
        break
    else
        echo "📊 More tickets still exist, continuing..."
    fi
    
    iteration=$((iteration + 1))
done

if [ $iteration -gt $MAX_ITERATIONS ]; then
    echo ""
    echo "⚠️  WARNING: Reached maximum iterations ($MAX_ITERATIONS)"
    echo "🔍 There may still be tickets remaining"
    echo "🔄 You can run this script again if needed"
fi

echo ""
echo "🏁 Deletion process completed"
echo "⏰ Finished at: $(date)"
