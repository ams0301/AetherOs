#!/bin/bash

# Create a test log file
LOG_FILE="/tmp/test-agent.log"
rm -f $LOG_FILE
touch $LOG_FILE

echo "Initial log file size: $(stat -c%s $LOG_FILE)"

# Start the probe in background and capture both stdout and stderr
cd /home/pc/.openclaw/workspace/aether-os/probe
OUTPUT_FILE="/tmp/probe_debug_output.txt"
echo "Starting probe..."
./bin/probe --log-file $LOG_FILE --window 3 --threshold 2 > $OUTPUT_FILE 2>&1 &
PROBE_PID=$!

echo "Probe started with PID: $PROBE_PID"
sleep 2  # Give probe time to start

echo "Log file size after probe start: $(stat -c%s $LOG_FILE)"

# Add some test data
echo "Adding test data..."
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE
echo "[exec] ls" >> $LOG_FILE
echo "[exec] error: command not found" >> $LOG_FILE

echo "Log file size after adding data: $(stat -c%s $LOG_FILE)"
sleep 3  # Give probe time to process

# Kill the probe
echo "Stopping probe..."
kill $PROBE_PID
wait $PROBE_PID 2>/dev/null
echo "Probe stopped."

echo "=== Probe Output ==="
cat $OUTPUT_FILE
echo "=== End Probe Output ==="

# Also check the log file content
echo "=== Log File Content ==="
cat $LOG_FILE
echo "=== End Log File Content ==="