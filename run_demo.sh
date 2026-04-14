#!/bin/bash
echo "=== Aether-OS Complete System Demonstration ==="
echo "Starting all three components in separate tmux panes..."
echo ""

# Create log file for demo
DEMO_LOG_FILE="/home/pc/.openclaw/workspace/aether-os/demo_logs/demo.log"
touch "$DEMO_LOG_FILE"

# Start Probe in background
echo "Starting Probe (monitoring current shell PID $$)..."
cd /home/pc/.openclaw/workspace/aether-os/probe/build
./aetheros-probe $$ > "$DEMO_LOG_FILE" 2>&1 &
PROBE_PID=$!
echo "Probe started with PID: $PROBE_PID"
echo "Probe logging to: $DEMO_LOG_FILE"
echo ""

# Give probe a moment to start
sleep 2

# Start Auditor in background  
echo "Starting Auditor (monitoring demo log file)..."
cd /home/pc/.openclaw/workspace/aether-os/auditor
python3 src/auditor.py --log-file "$DEMO_LOG_FILE" --probe-input > /home/pc/.openclaw/workspace/aether-os/demo_logs/auditor.log 2>&1 &
AUDITOR_PID=$!
echo "Auditor started with PID: $AUDITOR_PID"
echo "Auditor logging to: /home/pc/.openclaw/workspace/aether-os/demo_logs/auditor.log"
echo ""

# Give auditor a moment to start
sleep 2

# Start Controller in foreground (this will be the main interface)
echo "Starting Controller (main TUI interface)..."
cd /home/pc/.openclaw/workspace/aether-os/controller
echo "To see the system working:"
echo "1. Watch the probe output in terminal 1 (this terminal)"
echo "2. Check the auditor output in /home/pc/.openclaw/workspace/aether-os/demo_logs/auditor.log"
echo "3. The controller TUI should appear below in this same terminal"
echo ""
echo "In the controller TUI, you can:"
echo "- Use Monitoring tab to see live process data"
echo "- Use Snapshots tab to create/restore/delete snapshots" 
echo "- Use Policies tab to configure detection thresholds"
echo "- Use Audit Trail tab to view and export historical data"
echo "- Use Settings tab to adjust automation and sampling rates"
echo ""
echo "Try creating a snapshot of this shell (PID $$) to see the system in action!"
echo ""
echo "Press Ctrl+C in the controller to stop all components when done."
echo ""

# Start the controller (this will block until user exits)
python3 src/controller.py

# Cleanup when controller exits
echo ""
echo "Stopping all components..."
kill $PROBE_PID 2>/dev/null
kill $AUDITOR_PID 2>/dev/null
echo "Demo completed."