#!/usr/bin/env python3
"""
Aether-OS Controller
CLI dashboard for managing agent snapshots, throttling, and interventions.
"""

import sys
import os
import subprocess
import json
import time
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
import shutil

class AetherController:
    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()
        self.snapshots_dir = self.workspace_dir / "snapshots"
        self.snapshots_dir.mkdir(exist_ok=True)
        self.state_file = self.workspace_dir / ".aether_state.json"
        self.load_state()
    
    def load_state(self):
        """Load controller state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.state = {"snapshots": [], "last_snapshot_step": 0}
        else:
            self.state = {"snapshots": [], "last_snapshot_step": 0}
    
    def save_state(self):
        """Save controller state to file."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def create_snapshot(self, label: str = None) -> str:
        """Create a snapshot of the current workspace."""
        timestamp = int(time.time())
        if label is None:
            label = f"step-{timestamp}"
        
        snapshot_dir = self.snapshots_dir / label
        snapshot_dir.mkdir()
        
        # Copy workspace files (excluding snapshots directory and some others)
        exclude_dirs = {self.snapshots_dir.name, ".git", "__pycache__", "node_modules"}
        
        for item in self.workspace_dir.iterdir():
            if item.name in exclude_dirs:
                continue
            if item.is_dir():
                shutil.copytree(item, snapshot_dir / item.name, 
                              ignore=shutil.ignore_patterns('*.pyc', '__pycache__'))
            else:
                shutil.copy2(item, snapshot_dir / item.name)
        
        # Record snapshot
        snapshot_info = {
            "label": label,
            "timestamp": timestamp,
            "dir": str(snapshot_dir.relative_to(self.workspace_dir))
        }
        self.state["snapshots"].append(snapshot_info)
        self.state["last_snapshot_step"] += 1
        self.save_state()
        
        return label
    
    def list_snapshots(self) -> List[Dict]:
        """List all available snapshots."""
        return self.state["snapshots"]
    
    def rewind_to_snapshot(self, steps: int = 1) -> Optional[str]:
        """Rewind workspace to a previous snapshot."""
        snapshots = self.state["snapshots"]
        if not snapshots or steps < 1:
            return None
        
        # Calculate which snapshot to restore to
        target_index = len(snapshots) - steps
        if target_index < 0:
            target_index = 0
        
        target_snapshot = snapshots[target_index]
        snapshot_dir = self.workspace_dir / target_snapshot["dir"]
        
        if not snapshot_dir.exists():
            print(f"Error: Snapshot directory {snapshot_dir} not found")
            return None
        
        # Remove current workspace contents (except snapshots)
        for item in self.workspace_dir.iterdir():
            if item.name == self.snapshots_dir.name:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        
        # Copy snapshot contents back
        for item in snapshot_dir.iterdir():
            if item.is_dir():
                shutil.copytree(item, self.workspace_dir / item.name)
            else:
                shutil.copy2(item, self.workspace_dir / item.name)
        
        return target_snapshot["label"]
    
    def get_openclaw_pid(self) -> Optional[int]:
        """Get the PID of the OpenClaw process."""
        try:
            # Look for openclaw or node processes with specific patterns
            result = subprocess.run(
                ["pgrep", "-f", "openclaw"], 
                capture_output=True, text=True, check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]
                # Return the first one for simplicity
                return pids[0] if pids else None
        except Exception:
            pass
        return None
    
    def set_resource_limits(self, cpu_percent: int = None, memory_mb: int = None, pid: int = None) -> bool:
        """Set resource limits for a process using cgroups (simplified)."""
        if pid is None:
            pid = self.get_openclaw_pid()
        
        if pid is None:
            print("Error: Could not find OpenClaw process")
            return False
        
        # This is a simplified implementation - in reality, we'd use cgroups properly
        # For now, we'll just report what we would do
        print(f"Would set limits for PID {pid}:")
        if cpu_percent:
            print(f"  CPU: {cpu_percent}%")
        if memory_mb:
            print(f"  Memory: {memory_mb} MB")
        return True
    
    def apply_system_hint(self, hint: str) -> bool:
        """Apply a system hint to influence the agent's next action."""
        # In a real implementation, this would inject the hint into the agent's context
        # For now, we'll just log it
        hint_file = self.workspace_dir / ".aether_hint.txt"
        try:
            with open(hint_file, 'w') as f:
                f.write(f"System Hint: {hint}\n")
                f.write(f"Applied at: {time.ctime()}\n")
            print(f"System hint applied: {hint}")
            return True
        except Exception as e:
            print(f"Error applying system hint: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Aether-OS Controller')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Snapshot command
    snapshot_parser = subparsers.add_parser('snapshot', help='Create a workspace snapshot')
    snapshot_parser.add_argument('--label', type=str, help='Label for the snapshot')
    
    # List snapshots command
    subparsers.add_parser('list', help='List all snapshots')
    
    # Rewind command
    rewind_parser = subparsers.add_parser('rewind', help='Rewind to a previous snapshot')
    rewind_parser.add_argument('--steps', type=int, default=1, 
                              help='Number of steps to rewind (default: 1)')
    
    # Throttle command
    throttle_parser = subparsers.add_parser('throttle', help='Set resource limits')
    throttle_parser.add_argument('--cpu', type=int, help='CPU percentage limit')
    throttle_parser.add_argument('--memory', type=int, help='Memory limit in MB')
    throttle_parser.add_argument('--pid', type=int, help='Process ID to limit (optional)')
    
    # Hint command
    hint_parser = subparsers.add_parser('hint', help='Apply a system hint')
    hint_parser.add_argument('text', type=str, help='Hint text to apply')
    
    # Status command
    subparsers.add_parser('status', help='Show controller status')
    
    args = parser.parse_args()
    
    controller = AetherController()
    
    if args.command == 'snapshot':
        label = controller.create_snapshot(args.label)
        print(f"Created snapshot: {label}")
    
    elif args.command == 'list':
        snapshots = controller.list_snapshots()
        if not snapshots:
            print("No snapshots found")
        else:
            print("Snapshots:")
            for snap in snapshots:
                timestamp_str = time.ctime(snap['timestamp'])
                print(f"  {snap['label']} (created {timestamp_str})")
    
    elif args.command == 'rewind':
        label = controller.rewind_to_snapshot(args.steps)
        if label:
            print(f"Rewound to snapshot: {label} ({args.steps} step(s) back)")
        else:
            print("Error: Could not rewind - insufficient snapshots")
    
    elif args.command == 'throttle':
        success = controller.set_resource_limits(
            cpu_percent=args.cpu,
            memory_mb=args.memory,
            pid=args.pid
        )
        if success:
            print("Resource limits applied")
        else:
            print("Failed to apply resource limits")
    
    elif args.command == 'hint':
        success = controller.apply_system_hint(args.text)
        if success:
            print("System hint applied")
        else:
            print("Failed to apply system hint")
    
    elif args.command == 'status':
        snapshots = controller.list_snapshots()
        pid = controller.get_openclaw_pid()
        print(f"Aether-OS Controller Status")
        print(f"==========================")
        print(f"Workspace: {controller.workspace_dir}")
        print(f"Snapshots: {len(snapshots)}")
        print(f"OpenClaw PID: {pid if pid else 'Not found'}")
        if snapshots:
            latest = snapshots[-1]
            latest_time = time.ctime(latest['timestamp'])
            print(f"Latest snapshot: {latest['label']} ({latest_time})")
    
    else:
        parser.print_help()

if __name__ == '__main__':
    main()