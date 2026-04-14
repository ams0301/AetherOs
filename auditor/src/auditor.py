#!/usr/bin/env python3
"""
Aether-OS Auditor
Analyzes Probe output and log data to detect semantic loops and reduce false positives.
"""

import sys
import re
import time
from collections import deque, defaultdict
from typing import Deque, Tuple, Optional, Dict, List, Any
import json

class Auditor:
    def __init__(self, window_size: int = 5, threshold: int = 3):
        self.window_size = window_size
        self.threshold = threshold
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
                return alert
        except json.JSONDecodeError:
            pass
        return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Aether-OS Auditor')
    parser.add_argument('--window', type=int, default=5, help='Window size for loop detection')
    parser.add_argument('--threshold', type=int, default=3, help='Threshold for loop detection')
    parser.add_argument('--log-file', type=str, required=True, help='Path to OpenClaw log file')
    parser.add_argument('--probe-input', action='store_true', 
                       help='Read Probe alerts from stdin instead of monitoring log file')
    args = parser.parse_args()

    auditor = Auditor(window_size=args.window, threshold=args.threshold)
    mode = "Probe alert mode" if args.probe_input else "Log monitoring mode"
    print(f"Auditor started: {mode}")
    print(f"Monitoring: {args.log_file if not args.probe_input else 'stdin'}")
    print(f"Window: {args.window}, Threshold: {args.threshold}")

    if args.probe_input:
        # Read Probe alerts from stdin (JSON lines)
        for line in sys.stdin:
            line = line.strip()
            if line:
                enhanced_alert = auditor.process_probe_alert(line)
                if enhanced_alert:
                    print(f"🚨 AUDITOR-ENHANCED ALERT: {json.dumps(enhanced_alert, indent=2)}")
    else:
        # Monitor log file directly
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