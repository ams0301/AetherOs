#!/bin/bash

# Create a test log file
LOG_FILE="/tmp/simple-auditor.log"
rm -f $LOG_FILE
touch $LOG_FILE

# Start the auditor in background, capturing both stdout and stderr
cd /home/pc/.openclaw/workspace/aether-os/auditor
OUTPUT_FILE="/tmp/simple_auditor_output.txt"
python3 auditor.py --log-file $LOG_FILE --window 3 --threshold 2 > $OUTPUT_FILE 2>&1 &
AUDITOR_PID=$!

echo "Auditor started with PID: $AUDITOR_PID"
echo "Output (stdout+stderr) going to: $OUTPUT_FILE"

# Give it a moment to start
sleep 1

# Write test data that should trigger a syntactic loop
echo "Writing test data for syntactic loop..."
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE

# Wait for processing
sleep 3

# Kill the auditor
echo "Stopping auditor..."
kill $AUDITOR_PID
wait $AUDITOR_PID 2>/dev/null

echo "=== Auditor Output (stdout+stderr) ==="
cat $OUTPUT_FILE
echo "=== End Auditor Output ==="