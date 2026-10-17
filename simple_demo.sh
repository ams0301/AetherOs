#!/bin/bash
echo "=== Simple Aether-OS Demo ==="
echo "This will start all three components so you can see the system working"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create necessary directories
DEMO_LOG_DIR="$SCRIPT_DIR/demo_logs"
mkdir -p "$DEMO_LOG_DIR"
DEMO_LOG_FILE="$DEMO_LOG_DIR/demo.log"
touch "$DEMO_LOG_FILE"

# Start Probe (monitoring current shell)
echo "1. Starting Probe (monitoring shell PID $$)..."
cd "$SCRIPT_DIR/probe/build"
./aetheros-probe $$ > "$DEMO_LOG_FILE" 2>&1 &
PROBE_PID=$!
echo "   Probe PID: $PROBE_PID"
echo "   Logging to: $DEMO_LOG_FILE"
echo ""

# Wait a bit for probe to start
sleep 2

# Start Auditor (subscribing to the probe's ZMQ stream)
echo "2. Starting Auditor (subscribing to probe ZMQ stream)..."
cd "$SCRIPT_DIR/auditor"
python3 auditor.py --zmq > "$DEMO_LOG_DIR/auditor.log" 2>&1 &
AUDITOR_PID=$!
echo "   Auditor PID: $AUDITOR_PID"
echo "   Logging to: $DEMO_LOG_DIR/auditor.log"
echo ""

# Wait a bit for auditor to start
sleep 2

# Start Controller (this will be the interactive interface)
echo "3. Starting Controller (TUI interface - this will be interactive)..."
cd "$SCRIPT_DIR/controller/src"
echo ""
echo "=== CONTROLLER TUI STARTING BELOW ==="
echo "Use these tabs in the TUI:"
echo "  Monitoring: Live process data & alerts"
echo "  Snapshots: Create/list/restore/delete snapshots"
echo "  Policies: Configure detection thresholds & automation"
echo "  Audit Trail: View history, filter, acknowledge, export"
echo "  Settings: Adjust automation, sample rate, history size"
echo ""
echo "Press Ctrl+C in the Controller to stop all components when finished."
echo ""

# Start the controller
python3 controller.py

# Cleanup
echo ""
echo "Stopping all components..."
kill $PROBE_PID 2>/dev/null
kill $AUDITOR_PID 2>/dev/null
echo "Demo finished."