#!/bin/bash
echo "=== Aether-OS Complete System Demonstration ==="
echo "Starting all three components..."
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_LOG_DIR="$SCRIPT_DIR/demo_logs"
mkdir -p "$DEMO_LOG_DIR"
DEMO_LOG_FILE="$DEMO_LOG_DIR/demo.log"
touch "$DEMO_LOG_FILE"

# Start Probe in background
echo "Starting Probe (monitoring current shell PID $$)..."
cd "$SCRIPT_DIR/probe/build"
./aetheros-probe $$ > "$DEMO_LOG_FILE" 2>&1 &
PROBE_PID=$!
echo "Probe started with PID: $PROBE_PID"
echo "Probe logging to: $DEMO_LOG_FILE"
echo ""

# Give probe a moment to start
sleep 2

# Start Auditor in background (subscribes to the probe's ZMQ stream)
echo "Starting Auditor (subscribing to probe ZMQ stream)..."
cd "$SCRIPT_DIR/auditor"
python3 auditor.py --zmq > "$DEMO_LOG_DIR/auditor.log" 2>&1 &
AUDITOR_PID=$!
echo "Auditor started with PID: $AUDITOR_PID"
echo "Auditor logging to: $DEMO_LOG_DIR/auditor.log"
echo ""

# Give auditor a moment to start
sleep 2

# Start Controller in foreground (this will be the main interface)
echo "Starting Controller (main TUI interface)..."
cd "$SCRIPT_DIR/controller/src"
echo ""
echo "In the controller TUI, you can:"
echo "- Use Monitoring tab to see live process data"
echo "- Use Snapshots tab to create/restore/delete snapshots"
echo "- Use Policies tab to configure detection thresholds"
echo "- Use Audit Trail tab to view and export historical data"
echo "- Use Settings tab to adjust automation and sampling rates"
echo ""
echo "Press Ctrl+C in the controller to stop all components when done."
echo ""

# Start the controller (this will block until user exits)
python3 controller.py

# Cleanup when controller exits
echo ""
echo "Stopping all components..."
kill $PROBE_PID 2>/dev/null
kill $AUDITOR_PID 2>/dev/null
echo "Demo completed."