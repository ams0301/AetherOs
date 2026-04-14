#!/bin/bash

# Create a test log file
LOG_FILE="/tmp/test-agent.log"
rm -f $LOG_FILE
touch $LOG_FILE

# Start the probe in background and capture both stdout and stderr
cd /home/pc/.openclaw/workspace/aether-os/probe
OUTPUT_FILE="/tmp/probe_output_full.txt"
./bin/probe --log-file $LOG_FILE --window 3 --threshold 2 > $OUTPUT_FILE 2>&1 &
PROBE_PID=$!

echo "Probe started with PID: $PROBE_PID"
echo "Monitoring: $LOG_FILE"
echo "Generating test commands in background..."

# Simulate a loop: ls -> error -> ls
for i in {1..6}; do
    echo "[exec] ls" >> $LOG_FILE
    sleep 0.5
    echo "[exec] error: command not found" >> $LOG_FILE
    sleep 0.5
done

# Wait a bit for detection
sleep 3

# Kill the probe
kill $PROBE_PID
wait $PROBE_PID 2>/dev/null
echo "Probe stopped."

# Check if loop was detected in the output
if grep -q "LOOP DETECTED" $OUTPUT_FILE; then
    echo "✅ Test PASSED: Loop detected correctly"
    grep "LOOP DETECTED" $OUTPUT_FILE
else
    echo "❌ Test FAILED: Loop not detected"
    echo "Last 20 lines of probe output:"
    tail -20 $OUTPUT_FILE
fi