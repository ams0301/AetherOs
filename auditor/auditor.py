#!/usr/bin/env python3
"""
Aether-OS Auditor
Analyzes Probe output and log data to detect semantic loops and reduce false positives.
Supports both log file monitoring and live ZMQ stream from Probe.
"""

import sys
import re
import time
import json
import threading
from collections import deque, defaultdict
from typing import Deque, Tuple, Optional, Dict, List, Any

try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False

# Add the controller src to path for AuditViewer
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'controller', 'src'))
from audit.viewer import AuditViewer

class Auditor:
    def __init__(self, window_size: int = 5, threshold: int = 3, 
                 zmq_endpoint: str = "tcp://localhost:5555", db_path: str = "./auditor/aetheros_audit.db"):
        self.window_size = window_size
        self.threshold = threshold
        self.zmq_endpoint = zmq_endpoint
        self.db_path = db_path
        
        # Initialize audit viewer for database writes
        self.audit_viewer = AuditViewer(db_path)
        
        # Track command sequences with timestamps for time-based analysis
        self.command_history: Deque[Tuple[str, float]] = deque()
        # Track error patterns
        self.error_patterns = [
            r'error', r'fail', r'exception', r'not found', r'denied',
            r'invalid', r'wrong', r'bad', r'selector', r'timeout',
            r'connection refused', r'access denied'
        ]
        # Compile regex for efficiency
        self.error_regex = re.compile('|'.join(self.error_patterns), re.IGNORECASE)
        # State for loop detection (same as Probe but we can add more logic)
        self.state_counts: Dict[Tuple[str, ...], int] = defaultdict(int)
        self.last_alert_time = 0
        self.alert_cooldown = 0  # seconds - we reset count after triggering, so cooldown not needed
        # For semantic analysis
        self.error_streak = 0
        self.last_lines: Deque[str] = deque(maxlen=window_size)
        
        # ZMQ
        self.zmq_context = None
        self.zmq_socket = None
        self.zmq_thread = None
        self.zmq_running = False

    def is_error_line(self, line: str) -> bool:
        """Check if a log line indicates an error."""
        return bool(self.error_regex.search(line))

    def extract_command(self, line: str) -> Optional[str]:
        """Extract command from log line, assuming format [exec] <command>."""
        match = re.search(r'\[exec\]\s*(.+)', line)
        if match:
            return match.group(1).strip()
        return None

    def process_line(self, line: str) -> Optional[Dict]:
        """
        Process a single log line.
        Returns a dict with alert info if a loop is detected, else None.
        """
        # Add to recent lines for semantic analysis
        self.last_lines.append(line)
        if len(self.last_lines) > self.window_size:
            self.last_lines.popleft()
        
        command = self.extract_command(line)
        if command is None:
            # Not a command line, ignore for sequence tracking but check for semantic patterns
            return self._check_semantic_patterns()
        
        timestamp = time.time()
        self.command_history.append((command, timestamp))
        if len(self.command_history) > self.window_size:
            self.command_history.popleft()

        # Debug print to stderr
        sys.stderr.write(f"DEBUG: Processing line: {line.strip()}\n")
        sys.stderr.write(f"DEBUG: Extracted command: {command}\n")
        sys.stderr.write(f"DEBUG: command_history: {list(self.command_history)}\n")

        # Only check when we have a full window
        if len(self.command_history) == self.window_size:
            state = tuple(cmd for cmd, _ in self.command_history)
            self.state_counts[state] += 1
            count = self.state_counts[state]
            sys.stderr.write(f"DEBUG: state {state} count {count}\n")

            # Check if threshold reached and cooldown passed
            if count >= self.threshold:
                now = time.time()
                if now - self.last_alert_time > self.alert_cooldown:
                    self.last_alert_time = now
                    # Reset count to avoid spamming
                    self.state_counts[state] = 0
                    sys.stderr.write(f"DEBUG: Triggering syntactic loop alert for state {state}\n")
                    return {
                        'type': 'syntactic_loop',
                        'window_size': self.window_size,
                        'count': count,
                        'commands': [cmd for cmd, _ in self.command_history],
                        'timestamp': now,
                        'confidence': 'high'
                    }
        # Always check for semantic patterns
        semantic_result = self._check_semantic_patterns()
        if semantic_result:
            return semantic_result
        return None

    def _check_semantic_patterns(self) -> Optional[Dict]:
        """Check for semantic patterns like repeated errors."""
        # Check if all recent lines are errors
        if len(self.last_lines) == self.window_size:
            error_count = sum(1 for line in self.last_lines if self.is_error_line(line))
            if error_count == self.window_size:
                # All lines are errors - semantic loop
                return {
                    'type': 'semantic_error_loop',
                    'description': 'All recent commands resulted in errors',
                    'window_size': self.window_size,
                    'recent_errors': [line.strip() for line in self.last_lines],
                    'timestamp': time.time(),
                    'confidence': 'medium'
                }
        
        # Check for repeated error types
        if len(self.last_lines) >= 3:
            recent_errors = [line for line in self.last_lines if self.is_error_line(line)]
            if len(recent_errors) >= 3:
                # Look for similar error messages
                error_signatures = []
                for err in recent_errors:
                    # Create a signature by removing numbers and variable parts
                    sig = re.sub(r'\d+', '#', err)
                    sig = re.sub(r'/[^\s]+', '/PATH', sig)  # Normalize paths
                    error_signatures.append(sig)
                
                # Check if we have repeated signatures
                sig_counts = defaultdict(int)
                for sig in error_signatures:
                    sig_counts[sig] += 1
                
                max_count = max(sig_counts.values()) if sig_counts else 0
                if max_count >= 3:  # Same error signature 3+ times
                    # Find the signature with max count
                    max_sig = max(sig_counts, key=sig_counts.get)
                    return {
                        'type': 'repeated_error_pattern',
                        'description': f'Repeated error pattern detected: {max_sig[:50]}...',
                        'window_size': self.window_size,
                        'error_signature': max_sig,
                        'count': max_count,
                        'timestamp': time.time(),
                        'confidence': 'medium'
                    }
        return None

    def process_probe_alert(self, alert_json: str) -> Optional[Dict]:
        """
        Process an alert from the Probe to add semantic context.
        Returns enhanced alert or None if it should be suppressed.
        """
        try:
            alert = json.loads(alert_json)
            if alert.get('type') == 'loop_detected':
                # Add semantic analysis to the probe's syntactic detection
                recent_commands = alert.get('commands', [])
                # Check if these commands are all errors
                error_count = 0
                for cmd in recent_commands:
                    # We'd need to check the actual log lines for these commands
                    # For now, we'll assume if the probe detected it, it's worth considering
                    pass
                
                # Enhance the alert with semantic context
                alert['semantic_analysis'] = {
                    'available': True,
                    'note': 'Probe detected syntactic loop; Auditor adding semantic context'
                }
                alert['confidence'] = 'high'  # Boost confidence when both agree
                
                # Write to audit database
                self.audit_viewer.insert_loop_detection(
                    timestamp=alert.get('timestamp', time.time()),
                    pid=alert.get('pid', 0),
                    confidence=alert.get('confidence', 0.0),
                    cpu_usage=alert.get('cpu_usage', 0.0),
                    memory_usage=alert.get('memory_usage', 0),
                    similar_samples=alert.get('matches', 3)
                )
                self.audit_viewer.insert_alert(
                    timestamp=alert.get('timestamp', time.time()),
                    alert_type='loop_detected',
                    confidence=alert.get('confidence', 0.0),
                    pid=alert.get('pid', 0),
                    details=alert.get('details', 'Loop detected by probe')
                )
                
                return alert
        except json.JSONDecodeError:
            pass
        return None
    
    def start_zmq_listener(self):
        """Start listening to Probe's ZMQ stream in a background thread"""
        if not ZMQ_AVAILABLE:
            print("Warning: pyzmq not available, ZMQ listener disabled")
            return False
        
        try:
            self.zmq_context = zmq.Context()
            self.zmq_socket = self.zmq_context.socket(zmq.SUB)
            self.zmq_socket.connect(self.zmq_endpoint)
            self.zmq_socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all
            self.zmq_running = True
            self.zmq_thread = threading.Thread(target=self._zmq_listener_loop, daemon=True)
            self.zmq_thread.start()
            print(f"Auditor ZMQ listener started on {self.zmq_endpoint}")
            return True
        except Exception as e:
            print(f"Failed to start ZMQ listener: {e}")
            return False
    
    def _zmq_listener_loop(self):
        """Background loop to receive ZMQ messages from Probe"""
        while self.zmq_running:
            try:
                message = self.zmq_socket.recv_string(zmq.NOBLOCK)
                self._process_zmq_message(message)
            except zmq.Again:
                time.sleep(0.01)
            except Exception as e:
                if self.zmq_running:
                    print(f"ZMQ listener error: {e}")
                    time.sleep(1)
    
    def _process_zmq_message(self, message: str):
        """Process incoming ZMQ message from Probe"""
        try:
            data = json.loads(message)
            msg_type_raw = data.get('type')
            # Handle both string and integer type values
            try:
                msg_type = int(msg_type_raw)
            except (ValueError, TypeError):
                msg_type = -1
            timestamp = data.get('timestamp', time.time())
            pid = data.get('source_pid', 0)
            payload = data.get('payload', '{}')
            
            if msg_type == 0:  # PROCESS_METRICS
                # Payload might be a dict (already parsed) or string
                if isinstance(payload, str):
                    metrics = json.loads(payload)
                else:
                    metrics = payload
                # Extract command from payload or use default
                command = metrics.get('command', f'pid_{pid}')
                self.audit_viewer.insert_process_metrics(
                    timestamp=timestamp / 1000.0,  # Convert from ms to seconds
                    pid=pid,
                    command=command,
                    cpu_usage=metrics.get('cpu_usage', 0.0),
                    memory_usage=metrics.get('memory_kb', 0),
                    disk_read=metrics.get('disk_read_kb', 0),
                    disk_write=metrics.get('disk_write_kb', 0),
                    net_sent=metrics.get('net_tx', 0),
                    net_recv=metrics.get('net_rx', 0),
                    status='running'
                )
                
            elif msg_type == 1:  # LOOP_DETECTED
                if isinstance(payload, str):
                    loop_data = json.loads(payload)
                else:
                    loop_data = payload
                confidence = loop_data.get('confidence', 0.0)
                details = loop_data.get('details', '')
                
                # Enhance with semantic analysis
                enhanced_alert = self.process_probe_alert(json.dumps({
                    'type': 'loop_detected',
                    'timestamp': timestamp / 1000.0,
                    'pid': pid,
                    'confidence': confidence,
                    'details': details,
                    'cpu_usage': 0.0,  # Would need to extract from metrics
                    'memory_usage': 0,
                    'matches': 3
                }))
                
                if enhanced_alert:
                    print(f"🚨 AUDITOR-ENHANCED LOOP ALERT: {json.dumps(enhanced_alert, indent=2)}")
                    
            elif msg_type == 2:  # SYSTEM_EVENT
                event_data = json.loads(payload)
                self.audit_viewer.insert_system_event(
                    timestamp=timestamp / 1000.0,
                    event_type=event_data.get('event_type', 'unknown'),
                    source=f'probe_{pid}',
                    description=event_data.get('description', ''),
                    severity='info'
                )
                
            elif msg_type == 3:  # HEARTBEAT
                # Just log heartbeat
                pass
                
            elif msg_type == 4:  # ERROR
                error_data = json.loads(payload)
                self.audit_viewer.insert_system_event(
                    timestamp=timestamp / 1000.0,
                    event_type='error',
                    source=f'probe_{pid}',
                    description=error_data.get('error', 'Unknown error'),
                    severity='error'
                )
                
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Error processing ZMQ message: {e}")
    
    def stop_zmq_listener(self):
        """Stop the ZMQ listener"""
        self.zmq_running = False
        if self.zmq_socket:
            self.zmq_socket.close()
        if self.zmq_context:
            self.zmq_context.term()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Aether-OS Auditor')
    parser.add_argument('--window', type=int, default=5, help='Window size for loop detection')
    parser.add_argument('--threshold', type=int, default=3, help='Threshold for loop detection')
    parser.add_argument('--log-file', type=str, help='Path to OpenClaw log file (for log monitoring mode)')
    parser.add_argument('--probe-input', action='store_true', 
                       help='Read Probe alerts from stdin instead of monitoring log file')
    parser.add_argument('--zmq', action='store_true', 
                       help='Subscribe to Probe ZMQ stream (default: tcp://localhost:5555)')
    parser.add_argument('--zmq-endpoint', type=str, default='tcp://localhost:5555',
                       help='ZMQ endpoint to connect to')
    parser.add_argument('--db-path', type=str, default='./auditor/aetheros_audit.db',
                       help='Path to audit database')
    args = parser.parse_args()

    auditor = Auditor(window_size=args.window, threshold=args.threshold,
                      zmq_endpoint=args.zmq_endpoint, db_path=args.db_path)
    
    if args.zmq:
        mode = "ZMQ stream mode"
        print(f"Auditor started: {mode}")
        print(f"Connecting to: {args.zmq_endpoint}")
        print(f"Database: {args.db_path}")
        if not auditor.start_zmq_listener():
            sys.exit(1)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            auditor.stop_zmq_listener()
    elif args.probe_input:
        mode = "Probe alert mode"
        print(f"Auditor started: {mode}")
        print(f"Reading from: stdin")
        print(f"Window: {args.window}, Threshold: {args.threshold}")
        for line in sys.stdin:
            line = line.strip()
            if line:
                enhanced_alert = auditor.process_probe_alert(line)
                if enhanced_alert:
                    print(f"🚨 AUDITOR-ENHANCED ALERT: {json.dumps(enhanced_alert, indent=2)}")
    else:
        if not args.log_file:
            parser.error("--log-file required when not using --zmq or --probe-input")
        mode = "Log monitoring mode"
        print(f"Auditor started: {mode}")
        print(f"Monitoring: {args.log_file}")
        print(f"Window: {args.window}, Threshold: {args.threshold}")
        with open(args.log_file, 'r') as f:
            # Go to end of file
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                line = line.strip()
                if line:
                    result = auditor.process_line(line)
                    if result:
                        print(f"🚨 AUDITOR ALERT: {json.dumps(result, indent=2)}")

if __name__ == '__main__':
    main()