#!/bin/bash

# Create a test log file
LOG_FILE="/tmp/debug-auditor.log"
rm -f $LOG_FILE
touch $LOG_FILE

# Start the auditor in the foreground so we can see its output
cd /home/pc/.openclaw/workspace/aether-os/auditor
echo "Starting auditor in foreground (will run for 10 seconds)..."
timeout 10 python3 auditor.py --log-file $LOG_FILE --window 3 --threshold 2

# In another terminal, we would send data, but let's simulate by backgrounding a writer
# We'll do it in the same script by using two background processes and then killing them.

# Actually, let's do a simpler test: we'll write to the log file and then kill the auditor after a few seconds.

# We'll start the auditor in the background, write to the log, then kill it and check output.

LOG_FILE="/tmp/debug-auditor2.log"
rm -f $LOG_FILE
touch $LOG_FILE

cd /home/pc/.openclaw/workspace/aether-os/auditor
OUTPUT_FILE="/tmp/debug_auditor_output.txt"
python3 auditor.py --log-file $LOG_FILE --window 3 --threshold 2 > $OUTPUT_FILE 2>&1 &
AUDITOR_PID=$!
echo "Auditor PID: $AUDITOR_PID"

# Give it a moment to start
sleep 1

# Write test data
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE

sleep 2

# Kill the auditor
kill $AUDITOR_PID
wait $AUDITOR_PID 2>/dev/null

echo "=== Auditor Output ==="
cat $OUTPUT_FILE
echo "=== End Auditor Output ==="