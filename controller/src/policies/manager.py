"""
Policy Manager for Aether-OS Controller
Handles monitoring policies, thresholds, and automated responses
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class PolicyManager:
    def __init__(self, policy_dir: str = "./policies"):
        self.policy_dir = Path(policy_dir)
        self.policy_dir.mkdir(exist_ok=True)
        self.policies_file = self.policy_dir / "policies.json"
        self.policies = self._load_policies()
        
        # Ensure default policies exist
        self._ensure_default_policies()
    
    def _load_policies(self) -> Dict:
        """Load policies from file"""
        if self.policies_file.exists():
            try:
                with open(self.policies_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load policies: {e}")
                return {}
        return {}
    
    def _save_policies(self):
        """Save policies to file"""
        try:
            with open(self.policies_file, 'w') as f:
                json.dump(self.policies, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save policies: {e}")
    
    def _ensure_default_policies(self):
        """Ensure default policies exist"""
        defaults = {
            'loop_detection': {
                'enabled': True,
                'confidence_threshold': 0.8,
                'window_size': 5,
                'auto_pause': False,
                'auto_snapshot': True,
                'notification_level': 'warning'
            },
            'resource_thresholds': {
                'cpu_warning': 80.0,
                'cpu_critical': 95.0,
                'memory_warning': 80.0,
                'memory_critical': 95.0,
                'disk_warning': 90.0,
                'disk_critical': 98.0
            },
            'monitoring': {
                'sample_interval': 1.0,
                'history_size': 300,  # 5 minutes at 1Hz
                'alert_cooldown': 10.0,  # seconds
                'max_alerts_per_minute': 5
            },
            'automation': {
                'enabled': False,
                'max_concurrent_actions': 3,
                'action_timeout': 30.0
            }
        }
        
        for policy_name, default_policy in defaults.items():
            if policy_name not in self.policies:
                self.policies[policy_name] = default_policy
        
        self._save_policies()
    
    def get_policy(self, policy_name: str) -> Dict:
        """Get a policy by name"""
        return self.policies.get(policy_name, {})
    
    def set_policy(self, policy_name: str, policy_data: Dict):
        """Set a policy"""
        self.policies[policy_name] = policy_data
        self._save_policies()
        logger.info(f"Updated policy: {policy_name}")
    
    def update_policy(self, policy_name: str, updates: Dict):
        """Update specific fields in a policy"""
        if policy_name not in self.policies:
            self.policies[policy_name] = {}
        
        self.policies[policy_name].update(updates)
        self._save_policies()
        logger.info(f"Updated policy {policy_name}: {list(updates.keys())}")
    
    def delete_policy(self, policy_name: str) -> bool:
        """Delete a policy"""
        if policy_name in self.policies:
            del self.policies[policy_name]
            self._save_policies()
            logger.info(f"Deleted policy: {policy_name}")
            return True
        return False
    
    def list_policies(self) -> List[str]:
        """List all policy names"""
        return list(self.policies.keys())
    
    def evaluate_loop_detection(self, confidence: float, pid: int) -> Dict[str, Any]:
        """
        Evaluate loop detection against policies and return recommended actions
        
        Args:
            confidence: Loop detection confidence (0.0-1.0)
            pid: Process ID
            
        Returns:
            Dictionary with recommended actions
        """
        policy = self.get_policy('loop_detection')
        if not policy.get('enabled', True):
            return {'actions': []}
        
        threshold = policy.get('confidence_threshold', 0.8)
        actions = []
        
        if confidence >= threshold:
            actions.append({
                'type': 'alert',
                'level': policy.get('notification_level', 'warning'),
                'message': f'High confidence loop detection ({(confidence*100):.1f}%) for PID {pid}',
                'timestamp': datetime.now().isoformat()
            })
            
            if policy.get('auto_snapshot', False):
                actions.append({
                    'type': 'snapshot',
                    'pid': pid,
                    'description': f'Auto-snapshot due to loop detection (confidence: {confidence:.2f})',
                    'timestamp': datetime.now().isoformat()
                })
            
            if policy.get('auto_pause', False):
                actions.append({
                    'type': 'pause',
                    'pid': pid,
                    'reason': f'Loop detection exceeded threshold ({confidence:.2f} >= {threshold})',
                    'timestamp': datetime.now().isoformat()
                })
        
        return {'actions': actions}
    
    def evaluate_resource_usage(self, cpu_percent: float, memory_percent: float, 
                               disk_percent: float = 0.0) -> Dict[str, Any]:
        """
        Evaluate resource usage against policies
        
        Args:
            cpu_percent: CPU usage percentage
            memory_percent: Memory usage percentage
            disk_percent: Disk usage percentage
            
        Returns:
            Dictionary with recommended actions
        """
        policy = self.get_policy('resource_thresholds')
        actions = []
        
        # CPU checks
        if cpu_percent >= policy.get('cpu_critical', 95.0):
            actions.append({
                'type': 'alert',
                'level': 'critical',
                'message': f'Critical CPU usage: {cpu_percent:.1f}%',
                'timestamp': datetime.now().isoformat()
            })
        elif cpu_percent >= policy.get('cpu_warning', 80.0):
            actions.append({
                'type': 'alert',
                'level': 'warning',
                'message': f'High CPU usage: {cpu_percent:.1f}%',
                'timestamp': datetime.now().isoformat()
            })
        
        # Memory checks
        if memory_percent >= policy.get('memory_critical', 95.0):
            actions.append({
                'type': 'alert',
                'level': 'critical',
                'message': f'Critical memory usage: {memory_percent:.1f}%',
                'timestamp': datetime.now().isoformat()
            })
        elif memory_percent >= policy.get('memory_warning', 80.0):
            actions.append({
                'type': 'alert',
                'level': 'warning',
                'message': f'High memory usage: {memory_percent:.1f}%',
                'timestamp': datetime.now().isoformat()
            })
        
        # Disk checks
        if disk_percent >= policy.get('disk_critical', 98.0):
            actions.append({
                'type': 'alert',
                'level': 'critical',
                'message': f'Critical disk usage: {disk_percent:.1f}%',
                'timestamp': datetime.now().isoformat()
            })
        elif disk_percent >= policy.get('disk_warning', 90.0):
            actions.append({
                'type': 'alert',
                'level': 'warning',
                'message': f'High disk usage: {disk_percent:.1f}%',
                'timestamp': datetime.now().isoformat()
            })
        
        return {'actions': actions}
    
    def get_automation_settings(self) -> Dict:
        """Get automation settings"""
        return self.get_policy('automation')
    
    def set_automation_enabled(self, enabled: bool):
        """Enable or disable automation"""
        self.update_policy('automation', {'enabled': enabled})