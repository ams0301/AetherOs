#!/usr/bin/env python3
"""
Aether-OS Controller Component
CLI dashboard and control interface
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
import signal
import sys

# Add the src directory to the path so we can import our managers
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Button, DataTable, Label, Input, Static, TabbedContent, TabPane, Select, Switch
from textual.reactive import reactive
from textual.timer import Timer
import zmq
import zmq.asyncio

# Import our managers
from snapshots.manager import SnapshotManager
from policies.manager import PolicyManager
from audit.viewer import AuditViewer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProcessInfoWidget(Static):
    """Widget to display process information"""
    
    def compose(self) -> ComposeResult:
        yield Label("Process Information", id="process-title")
        yield DataTable(id="process-table")


class AlertWidget(Static):
    """Widget to display alerts"""
    
    def compose(self) -> ComposeResult:
        yield Label("Alerts", id="alert-title")
        yield DataTable(id="alert-table")


class ControlWidget(Static):
    """Widget for manual controls"""
    
    def compose(self) -> ComposeResult:
        yield Label("Controls", id="control-title")
        yield Button("Pause Process", id="pause-btn", variant="warning")
        yield Button("Resume Process", id="resume-btn", variant="success")
        yield Button("Terminate Process", id="terminate-btn", variant="error")
        yield Button("Create Snapshot", id="snapshot-btn", variant="primary")
        yield Input(placeholder="Target PID", id="pid-input")
        yield Label("Status: Ready", id="status-label")


class AetherOSController(App):
    """Main Aether-OS Controller Application"""
    
    CSS = """
    Screen {
        layout: vertical;
        overflow: auto;
    }
    
    #process-table, #alert-table {
        height: 20;
    }
    
    .panel {
        height: 1fr;
        border: solid white;
        margin: 1;
        padding: 1;
    }
    
    #controls {
        height: auto;
    }
    
    Button {
        margin: 0 1;
    }
    
    #pid-input {
        width: 20;
        margin: 1;
    }
    """
    
    def __init__(self):
        super().__init__()
        self.process_data = []
        self.alert_data = []
        self.target_pid = None
        self.running = True
        self.zmq_context = None
        self.zmq_socket = None
        
        # Initialize managers
        self.snapshot_manager = SnapshotManager()
        self.policy_manager = PolicyManager()
        self.audit_viewer = AuditViewer()
        
    def compose(self) -> ComposeResult:
        yield Header()
        yield TabbedContent(
            TabPane(
                "Monitoring",
                Container(
                    Horizontal(
                        Vertical(
                            ProcessInfoWidget(),
                            id="process-panel",
                            classes="panel"
                        ),
                        Vertical(
                            AlertWidget(),
                            id="alert-panel",
                            classes="panel"
                        ),
                    ),
                    Vertical(
                        ControlWidget(),
                        id="controls",
                        classes="panel"
                    ),
                    id="monitoring-content"
                ),
            ),
            TabPane(
                "Snapshots",
                Container(
                    Vertical(
                        Label("Snapshot Management", id="snapshot-title"),
                        Button("Refresh List", id="refresh-snapshots-btn", variant="default"),
                        Button("Create Snapshot", id="create-snapshot-btn", variant="primary"),
                        Button("Restore Snapshot", id="restore-snapshot-btn", variant="success"),
                        Button("Delete Snapshot", id="delete-snapshot-btn", variant="error"),
                        DataTable(id="snapshots-table"),
                        Input(placeholder="Snapshot ID or Description", id="snapshot-search-input"),
                        Label("Status: Ready", id="snapshot-status-label"),
                    ),
                    id="snapshots-content"
                ),
            ),
            TabPane(
                "Policies",
                Container(
                    Vertical(
                        Label("Policy Management", id="policy-title"),
                        Button("Refresh Policies", id="refresh-policies-btn", variant="default"),
                        Button("Add Policy", id="add-policy-btn", variant="primary"),
                        Button("Edit Policy", id="edit-policy-btn", variant="warning"),
                        Button("Delete Policy", id="delete-policy-btn", variant="error"),
                        DataTable(id="policies-table"),
                        Input(placeholder="Policy Name", id="policy-search-input"),
                        Label("Status: Ready", id="policy-status-label"),
                    ),
                    id="policies-content"
                ),
            ),
            TabPane(
                "Audit Trail",
                Container(
                    Vertical(
                        Label("Audit Trail Viewer", id="audit-title"),
                        Button("Refresh Data", id="refresh-audit-btn", variant="default"),
                        Button("Export JSON", id="export-json-btn", variant="primary"),
                        Button("Export CSV", id="export-csv-btn", variant="success"),
                        Button("Acknowledge Alerts", id="acknowledge-alerts-btn", variant="warning"),
                        DataTable(id="audit-table"),
                        Input(placeholder="Filter (time, type, etc.)", id="audit-filter-input"),
                        Label("Status: Ready", id="audit-status-label"),
                    ),
                    id="audit-content"
                ),
            ),
            TabPane(
                "Settings",
                Container(
                    Vertical(
                        Label("System Settings", id="settings-title"),
                        Switch("Enable Automation", id="automation-switch"),
                        Label("Sample Interval (seconds):"),
                        Input(placeholder="1.0", id="sample-interval-input"),
                        Label("History Size (samples):"),
                        Input(placeholder="300", id="history-size-input"),
                        Button("Save Settings", id="save-settings-btn", variant="primary"),
                        Label("Status: Ready", id="settings-status-label"),
                    ),
                    id="settings-content"
                ),
            ),
        )
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize when app mounts"""
        # Setup process table
        process_table = self.query_one("#process-table", DataTable)
        process_table.add_columns("PID", "Command", "CPU%", "Memory (KB)", "Status")
        
        # Setup alert table
        alert_table = self.query_one("#alert-table", DataTable)
        alert_table.add_columns("Time", "Type", "Confidence", "Details")
        
        # Setup snapshots table
        snapshots_table = self.query_one("#snapshots-table", DataTable)
        snapshots_table.add_columns("ID", "PID", "Timestamp", "Description", "Size")
        
        # Setup policies table
        policies_table = self.query_one("#policies-table", DataTable)
        policies_table.add_columns("Name", "Type", "Enabled", "Description")
        
        # Setup audit table
        audit_table = self.query_one("#audit-table", DataTable)
        audit_table.add_columns("Time", "Type", "PID", "Confidence", "Details")
        
        # Setup ZMQ communication
        self.setup_zmq()
        
        # Start update timers
        self.set_interval(1.0, self.update_display)  # Main display update
        self.set_interval(5.0, self.refresh_snapshots)  # Snapshot refresh
        self.set_interval(5.0, self.refresh_policies)   # Policy refresh
        self.set_interval(10.0, self.refresh_audit)     # Audit refresh
        
        logger.info("Aether-OS Controller started")
    
    def setup_zmq(self):
        """Setup ZeroMQ communication with Probe and Auditor"""
        try:
            self.zmq_context = zmq.asyncio.Context()
            self.zmq_socket = self.zmq_context.socket(zmq.SUB)
            self.zmq_socket.connect("tcp://localhost:5555")  # Publisher from Probe/Auditor
            self.zmq_socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all
            logger.info("ZMQ setup complete")
        except Exception as e:
            logger.error(f"Failed to setup ZMQ: {e}")
    
    async def listen_zmq(self):
        """Listen for ZMQ messages in background"""
        while self.running:
            try:
                if self.zmq_socket:
                    message = await self.zmq_socket.recv_string()
                    await self.process_zmq_message(message)
            except zmq.Again:
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"ZMQ error: {e}")
                await asyncio.sleep(1)
    
    async def process_zmq_message(self, message: str):
        """Process incoming ZMQ message"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'process_info':
                self.process_data = data.get('data', [])
            elif msg_type == 'alert':
                self.alert_data.append(data.get('data', {}))
                # Keep only last 50 alerts
                if len(self.alert_data) > 50:
                    self.alert_data = self.alert_data[-50:]
            elif msg_type == 'loop_detection':
                # Handle loop detection specifically
                alert = {
                    'time': datetime.now().strftime("%H:%M:%S"),
                    'type': 'LOOP_DETECTED',
                    'confidence': f"{data.get('confidence', 0):.2f}",
                    'details': f"PID: {data.get('pid', 'unknown')}"
                }
                self.alert_data.append(alert)
                if len(self.alert_data) > 50:
                    self.alert_data = self.alert_data[-50:]
                    
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received: {message[:100]}")
        except Exception as e:
            logger.error(f"Error processing ZMQ message: {e}")
    
    def update_display(self):
        """Update the display with latest data"""
        try:
            # Update process table
            process_table = self.query_one("#process-table", DataTable)
            process_table.clear()
            
            for proc in self.process_data[-10:]:  # Show last 10 processes
                process_table.add_row(
                    proc.get('pid', ''),
                    proc.get('command', '')[:30],
                    f"{proc.get('cpu_usage', 0):.1f}",
                    proc.get('memory_usage', 0),
                    proc.get('status', 'running')
                )
            
            # Update alert table
            alert_table = self.query_one("#alert-table", DataTable)
            alert_table.clear()
            
            for alert in self.alert_data[-10:]:  # Show last 10 alerts
                alert_table.add_row(
                    alert.get('time', ''),
                    alert.get('type', ''),
                    alert.get('confidence', ''),
                    alert.get('details', '')[:40]
                )
                
        except Exception as e:
            logger.error(f"Error updating display: {e}")
    
    def refresh_snapshots(self):
        """Refresh the snapshots table"""
        try:
            snapshots_table = self.query_one("#snapshots-table", DataTable)
            snapshots_table.clear()
            
            snapshots = self.snapshot_manager.list_snapshots()
            for snapshot in snapshots[:20]:  # Show last 20 snapshots
                size_mb = snapshot.get('size', 0) / (1024 * 1024) if snapshot.get('size') else 0
                snapshots_table.add_row(
                    snapshot.get('id', ''),
                    snapshot.get('pid', ''),
                    snapshot.get('timestamp', ''),
                    snapshot.get('description', '')[:30],
                    f"{size_mb:.1f} MB" if size_mb > 0 else "N/A"
                )
                
        except Exception as e:
            logger.error(f"Error refreshing snapshots: {e}")
    
    def refresh_policies(self):
        """Refresh the policies table"""
        try:
            policies_table = self.query_one("#policies-table", DataTable)
            policies_table.clear()
            
            for policy_name in self.policy_manager.list_policies():
                policy = self.policy_manager.get_policy(policy_name)
                policies_table.add_row(
                    policy_name,
                    policy_name.replace('_', ' ').title(),
                    "Yes" if policy.get('enabled', True) else "No",
                    str(policy)[:50] + "..." if len(str(policy)) > 50 else str(policy)
                )
                
        except Exception as e:
            logger.error(f"Error refreshing policies: {e}")
    
    def refresh_audit(self):
        """Refresh the audit table"""
        try:
            audit_table = self.query_one("#audit-table", DataTable)
            audit_table.clear()
            
            # Get recent alerts and loop detections
            alerts = self.audit_viewer.get_alerts(limit=10)
            loops = self.audit_viewer.get_loop_detections(limit=10)
            
            # Combine and sort by timestamp
            combined = []
            for alert in alerts:
                combined.append({
                    'time': datetime.fromtimestamp(alert['timestamp']).strftime("%H:%M:%S"),
                    'type': alert['alert_type'],
                    'pid': alert.get('pid', 'N/A'),
                    'confidence': f"{alert.get('confidence', 0):.2f}" if alert.get('confidence') else 'N/A',
                    'details': alert.get('details', '')[:30]
                })
            
            for loop in loops:
                combined.append({
                    'time': datetime.fromtimestamp(loop['timestamp']).strftime("%H:%M:%S"),
                    'type': 'LOOP_DETECTION',
                    'pid': loop.get('pid', 'N/A'),
                    'confidence': f"{loop.get('confidence', 0):.2f}",
                    'details': f"CPU: {loop.get('cpu_usage', 0):.1f}%, Mem: {loop.get('memory_usage', 0)//1024}MB"
                })
            
            # Sort by time (newest first)
            combined.sort(key=lambda x: x['time'], reverse=True)
            
            for item in combined[:20]:  # Show last 20 entries
                audit_table.add_row(
                    item['time'],
                    item['type'],
                    item['pid'],
                    item['confidence'],
                    item['details']
                )
                
        except Exception as e:
            logger.error(f"Error refreshing audit: {e}")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button_id = event.button.id
        
        if button_id == "pause-btn":
            self.pause_process()
        elif button_id == "resume-btn":
            self.resume_process()
        elif button_id == "terminate-btn":
            self.terminate_process()
        elif button_id == "snapshot-btn":
            self.create_snapshot()
        elif button_id == "refresh-snapshots-btn":
            self.refresh_snapshots()
        elif button_id == "create-snapshot-btn":
            self.create_snapshot_from_ui()
        elif button_id == "restore-snapshot-btn":
            self.restore_snapshot_from_ui()
        elif button_id == "delete-snapshot-btn":
            self.delete_snapshot_from_ui()
        elif button_id == "refresh-policies-btn":
            self.refresh_policies()
        elif button_id == "add-policy-btn":
            self.add_policy_from_ui()
        elif button_id == "edit-policy-btn":
            self.edit_policy_from_ui()
        elif button_id == "delete-policy-btn":
            self.delete_policy_from_ui()
        elif button_id == "refresh-audit-btn":
            self.refresh_audit()
        elif button_id == "export-json-btn":
            self.export_audit_json()
        elif button_id == "export-csv-btn":
            self.export_audit_csv()
        elif button_id == "acknowledge-alerts-btn":
            self.acknowledge_alerts()
        elif button_id == "save-settings-btn":
            self.save_settings()
    
    def pause_process(self):
        """Pause the target process"""
        pid_input = self.query_one("#pid-input", Input)
        try:
            pid = int(pid_input.value) if pid_input.value else self.target_pid
            if pid:
                import os
                os.kill(pid, signal.SIGSTOP)
                self.update_status(f"Process {pid} paused")
                logger.info(f"Paused process {pid}")
            else:
                self.update_status("Please enter a PID")
        except ValueError:
            self.update_status("Please enter a valid PID number")
    
    def resume_process(self):
        """Resume the target process"""
        pid_input = self.query_one("#pid-input", Input)
        try:
            pid = int(pid_input.value) if pid_input.value else self.target_pid
            if pid:
                import os
                os.kill(pid, signal.SIGCONT)
                self.update_status(f"Process {pid} resumed")
                logger.info(f"Resumed process {pid}")
            else:
                self.update_status("Please enter a PID")
        except ValueError:
            self.update_status("Please enter a valid PID number")
    
    def terminate_process(self):
        """Terminate the target process"""
        pid_input = self.query_one("#pid-input", Input)
        try:
            pid = int(pid_input.value) if pid_input.value else self.target_pid
            if pid:
                import os
                os.kill(pid, signal.SIGTERM)
                self.update_status(f"Process {pid} terminated")
                logger.info(f"Terminated process {pid}")
            else:
                self.update_status("Please enter a PID")
        except ValueError:
            self.update_status("Please enter a valid PID number")
    
    def create_snapshot(self):
        """Create a snapshot of current process"""
        # Simple implementation - would normally get PID from input or config
        self.update_status("Snapshot created (placeholder)")
        logger.info("Create snapshot requested")

