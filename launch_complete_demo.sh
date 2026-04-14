#!/bin/bash
echo "🚀 LAUNCHING COMPLETE AETHER-OS DEMONSTRATION"
echo "This will start all three components in separate tmux panes"
echo ""

# Create demo log directory
mkdir -p /home/pc/.openclaw/workspace/aether-os/demo_logs
DEMO_LOG="/home/pc/.openclaw/workspace/aether-os/demo_logs/probe_demo.log"
touch "$DEMO_LOG"

# Start Probe in tmux pane 1
echo "Starting Probe (monitoring current shell)..."
tmux new-session -d -s aetheros-demo 'cd /home/pc/.openclaw/workspace/aether-os/probe/build && ./aetheros-probe $$' \; \
  rename-window 'PROBE-MONITOR'

# Wait for probe to start
sleep 2

# Start Auditor in tmux pane 2  
tmux split-window -h -t aetheros-demo 'cd /home/pc/.openclaw/workspace/aether-os/auditor && python3 src/auditor.py --log-file '"$DEMO_LOG"' --window 3 --threshold 2' \; \
  select-pane -t 1 \; \
  rename-window 'AUDITOR-ANALYSIS'

# Wait for auditor to start
sleep 2

# Start Controller in tmux pane 3 (main interface)
tmux split-window -v -t aetheros-demo 'cd /home/pc/.openclaw/workspace/aether-os/controller && python3 src/controller.py' \; \
  select-pane -t 2 \; \
  rename-window 'CONTROLLER-INTERFACE'

# Select the controller pane (where user will interact)
tmux select-pane -t 2

echo ""
echo "🎯 AETHER-OS DEMO IS NOW RUNNING!"
echo ""
echo "📋 PANEL LAYOUT:"
echo "  [PANEL 1] PROBE-MONITOR:  Real-time process monitoring"
echo "  [PANEL 2] AUDITOR-ANALYSIS: Loop/anomaly detection & alerts" 
echo "  [PANEL 3] CONTROLLER-INTERFACE: Full TUI interface (YOU CONTROL THIS)"
echo ""
echo "🎮 IN THE CONTROLLER (PANEL 3), TRY:"
echo "   1. Go to SNAPSHOTS tab"
echo "   2. Enter PID: $$ (current shell PID)"
echo "   3. Description: 'Demo test snapshot'"
echo "   4. Click 'CREATE SNAPSHOT'"
echo "   5. Go to AUDIT TRAIL tab to see the recorded event"
echo "   6. Go to POLICIES tab to adjust detection thresholds"
echo "   7. Go to SETTINGS tab to configure automation"
echo ""
echo "💡 TIPS:"
echo "   - Use Ctrl+b then [arrow keys] to navigate between tmux panes"
echo "   - In controller: Use Tab to navigate between fields, Enter to activate buttons"
echo "   - Press Ctrl+C in the controller to gracefully shutdown all components"
echo ""
echo "🌟 THE SYSTEM IS NOW FULLY OPERATIONAL - ENJOY!"
echo ""

# Attach to the tmux session
tmux attach-session -t aetheros-demo

# Cleanup on exit
echo ""
echo "🛑 Stopping all Aether-OS components..."
tmux kill-session -t aetheros-demo 2>/dev/null
echo "✅ Demo completed successfully!"