#!/bin/bash
echo "LAUNCHING COMPLETE AETHER-OS DEMONSTRATION"
echo "This will start all three components in separate tmux panes"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create demo log directory
DEMO_LOG_DIR="$SCRIPT_DIR/demo_logs"
mkdir -p "$DEMO_LOG_DIR"
DEMO_LOG="$DEMO_LOG_DIR/probe_demo.log"
touch "$DEMO_LOG"

# Start Probe in tmux pane 1
echo "Starting Probe (monitoring current shell)..."
tmux new-session -d -s aetheros-demo "cd '$SCRIPT_DIR/probe/build' && ./aetheros-probe \$\$" \; \
  rename-window 'PROBE-MONITOR'

# Wait for probe to start
sleep 2

# Start Auditor in tmux pane 2 (subscribing to the probe's ZMQ stream)
tmux split-window -h -t aetheros-demo "cd '$SCRIPT_DIR/auditor' && python3 auditor.py --zmq --window 3 --threshold 2" \; \
  select-pane -t 1 \; \
  rename-window 'AUDITOR-ANALYSIS'

# Wait for auditor to start
sleep 2

# Start Controller in tmux pane 3 (main interface)
tmux split-window -v -t aetheros-demo "cd '$SCRIPT_DIR/controller/src' && python3 controller.py" \; \
  select-pane -t 2 \; \
  rename-window 'CONTROLLER-INTERFACE'

# Select the controller pane (where user will interact)
tmux select-pane -t 2

echo ""
echo "AETHER-OS DEMO IS NOW RUNNING!"
echo ""
echo "PANEL LAYOUT:"
echo "  [PANEL 1] PROBE-MONITOR:  Real-time process monitoring"
echo "  [PANEL 2] AUDITOR-ANALYSIS: Loop/anomaly detection & alerts"
echo "  [PANEL 3] CONTROLLER-INTERFACE: Full TUI interface (YOU CONTROL THIS)"
echo ""
echo "TIPS:"
echo "   - Use Ctrl+b then [arrow keys] to navigate between tmux panes"
echo "   - In controller: Use Tab to navigate between fields, Enter to activate buttons"
echo ""
echo "THE SYSTEM IS NOW FULLY OPERATIONAL - ENJOY!"
echo ""

# Attach to the tmux session
tmux attach-session -t aetheros-demo

# Cleanup on exit
echo ""
echo "Stopping all Aether-OS components..."
tmux kill-session -t aetheros-demo 2>/dev/null
echo "Demo completed successfully!"