#!/bin/bash

# Create a test log file
LOG_FILE="/tmp/test-auditor.log"
rm -f $LOG_FILE
touch $LOG_FILE

# Start the auditor in background and capture its output
cd /home/pc/.openclaw/workspace/aether-os/auditor
OUTPUT_FILE="/tmp/auditor_output.txt"
python3 auditor.py --log-file $LOG_FILE --window 3 --threshold 2 > $OUTPUT_FILE 2>&1 &
AUDITOR_PID=$!

echo "Auditor started with PID: $AUDITOR_PID"
echo "Monitoring: $LOG_FILE"
echo "Generating test commands in background..."

# Test 1: Syntactic loop (same as probe test)
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE

sleep 2

# Test 2: Semantic error loop (all errors, different commands)
echo "[exec] error: timeout" >> $LOG_FILE
echo "[exec] error: connection refused" >> $LOG_FILE
echo "[exec] error: access denied" >> $LOG_FILE

sleep 2

# Test 3: Repeated error pattern (similar errors)
echo "[exec] SelectorNotFound: #div-id" >> $LOG_FILE
echo "[exec] SelectorNotFound: #button-class" >> $LOG_FILE
echo "[exec] SelectorNotFound: [name=submit]" >> $LOG_FILE

sleep 2

# Kill the auditor
kill $AUDITOR_PID
wait $AUDITOR_PID 2>/dev/null
echo "Auditor stopped."

echo "=== Auditor Output ==="
cat $OUTPUT_FILE
echo "=== End Auditor Output ==="

# Check for expected alerts
if grep -q "syntactic_loop" $OUTPUT_FILE || grep -q "semantic_error_loop" $OUTPUT_FILE || grep -q "repeated_error_pattern" $OUTPUT_FILE; then
    echo "✅ Test PASSED: Auditor detected expected patterns"
else
    echo "❌ Test FAILED: No expected patterns detected"
fi