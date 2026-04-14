# Controller Component

CLI dashboard and control interface for Aether-OS.

## Responsibilities
- Display real-time monitoring data from Probe and Auditor
- Provide manual intervention controls (pause, terminate, rewind)
- Configure monitoring policies and thresholds
- Visualize agent behavior patterns and resource usage
- Manage snapshots and rollback operations
- Send commands to Probe and Auditor components
- Display audit trails and compliance reports

## Key Features
- Real-time TUI dashboard (using Ncurses or similar)
- Process tree visualization with resource metrics
- Loop detection alerts with confidence scores
- Manual control: SIGSTOP, SIGCONT, SIGTERM
- Snapshot management (create, list, restore)
- Policy configuration (resource limits, check frequency)
- Audit trail viewer with filtering and search
- Export capabilities (CSV, JSON reports)
- Configuration persistence

## Implementation Plan
1. Basic TUI framework with live updating panels
2. Process monitoring display (CPU, memory, PID, command)
3. Alert display for detected anomalies/loops
4. Control buttons for process manipulation
5. Snapshot management interface
6. Policy configuration screens
7. Audit trail viewer with temporal navigation
8. Communication layer with Probe/Auditor (Unix sockets, MQTT, or REST)
9. Configuration persistence (JSON/YAML)

## Dependencies
- Python 3.8+ (if using Python-based TUI like textual or urwid)
  OR
- C++ with Ncurses library
- Optional: textual (modern Python TUI framework)
- Optional: urwid (classic Python TUI)
- Optional: rich (for rich text formatting in terminal)
- Optional: pyzmq or similar for IPC
- Optional: matplotlib for embedding simple charts