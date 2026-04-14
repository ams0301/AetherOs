#!/bin/bash
echo "=== Simple Aether-OS Demo ==="
echo "This will start all three components so you can see the system working"
echo ""

# Create necessary directories
mkdir -p /home/pc/.openclaw/workspace/aether-os/demo_logs
DEMO_LOG_FILE="/home/pc/.openclaw/workspace/aether-os/demo_logs/demo.log"
touch "$DEMO_LOG_FILE"

# Start Probe (monitoring current shell)
echo "1. Starting Probe (monitoring shell PID $$)..."
cd /home/pc/.openclaw/workspace/aether-os/probe/build
./aetheros-probe $$ > "$DEMO_LOG_FILE" 2>&1 &
PROBE_PID=$!
echo "   Probe PID: $PROBE_PID"
echo "   Logging to: $DEMO_LOG_FILE"
echo ""

# Wait a bit for probe to start
sleep 2

# Start Auditor (monitoring the log file)
echo "2. Starting Auditor (monitoring demo log)..."
cd /home/pc/.openclaw/workspace/aether-os/auditor
python3 src/auditor.py --log-file "$DEMO_LOG_FILE" > /home/pc/.openclaw/workspace/aether-os/demo_logs/auditor.log 2>&1 &
AUDITOR_PID=$!
echo "   Auditor PID: $AUDITOR_PID"
echo "   Logging to: /home/pc/.openclaw/workspace/aether-os/demo_logs/auditor.log"
echo ""

# Wait a bit for auditor to start
sleep 2

# Start Controller (this will be the interactive interface)
echo "3. Starting Controller (TUI interface - this will be interactive)..."
cd /home/pc/.openclaw/workspace/aether-os/controller
echo ""
echo "=== CONTROLLER TUI STARTING BELOW ==="
echo "Use these tabs in the TUI:"
echo "  📊 Monitoring: Live process data & alerts"
echo "  📸 Snapshots: Create/list/restore/delete snapshots"
echo "  ⚙️  Policies: Configure detection thresholds & automation"
echo "  📋 Audit Trail: View history, filter, acknowledge, export"
echo "  ⚙️  Settings: Adjust automation, sample rate, history size"
echo ""
echo "Try this in the Controller:"
echo "  1. Go to Snapshots tab"
echo "  2. Enter PID: $$ (this shell's PID)"
echo "  3. Enter description: 'Demo snapshot of shell'"
echo "  4. Click 'Create Snapshot'"
echo "  5. Go to Audit Trail tab to see the event"
echo ""
echo "Press Ctrl+C in the Controller to stop all components when finished."
echo ""

# Start the controller
python3 src/controller.py

# Cleanup
echo ""
echo "Stopping all components..."
kill $PROBE_PID 2>/dev/null
kill $AUDITOR_PID 2>/dev/null
echo "Demo finished."