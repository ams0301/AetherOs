"""
Audit Trail Viewer for Aether-OS Controller
Provides filtering, searching, and visualization of audit data
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class AuditViewer:
    def __init__(self, db_path: str = "./auditor/aetheros_audit.db"):
        self.db_path = Path(db_path)
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Ensure audit database exists, create if needed"""
        if not self.db_path.exists():
            logger.warning(f"Audit database not found at {self.db_path}")
            # Create a minimal schema for demonstration
            self._create_demo_schema()
    
    def _create_demo_schema(self):
        """Create demo database schema"""
        self.db_path.parent.mkdir(exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            
            # Process metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS process_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    pid INTEGER,
                    command TEXT,
                    cpu_usage REAL,
                    memory_usage INTEGER,
                    disk_read INTEGER,
                    disk_write INTEGER,
                    net_sent INTEGER,
                    net_recv INTEGER,
                    status TEXT
                )
            """)
            
            # System events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    event_type TEXT,
                    source TEXT,
                    description TEXT,
                    severity TEXT
                )
            """)
            
            # Alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    alert_type TEXT,
                    confidence REAL,
                    pid INTEGER,
                    details TEXT,
                    acknowledged BOOLEAN DEFAULT 0
                )
            """)
            
            # Loop detections table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS loop_detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    pid INTEGER,
                    confidence REAL,
                    cpu_usage REAL,
                    memory_usage INTEGER,
                    similar_samples INTEGER
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_process_timestamp ON process_metrics(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_loop_timestamp ON loop_detections(timestamp)")
            
            conn.commit()
            logger.info("Created demo audit database schema")
            
        except Exception as e:
            logger.error(f"Failed to create demo schema: {e}")
        finally:
            conn.close()
    
    def get_process_metrics(self, 
                           start_time: Optional[float] = None,
                           end_time: Optional[float] = None,
                           pid: Optional[int] = None,
                           limit: int = 1000) -> List[Dict]:
        """
        Get process metrics from audit database
        
        Args:
            start_time: Start timestamp (Unix time)
            end_time: End timestamp (Unix time)
            pid: Filter by process ID
            limit: Maximum number of records
            
        Returns:
            List of process metric dictionaries
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM process_metrics WHERE 1=1"
            params = []
            
            if start_time is not None:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time is not None:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            if pid is not None:
                query += " AND pid = ?"
                params.append(pid)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append(dict(row))
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to get process metrics: {e}")
            return []
    
    def get_alerts(self,
                  start_time: Optional[float] = None,
                  end_time: Optional[float] = None,
                  alert_type: Optional[str] = None,
                  acknowledged: Optional[bool] = None,
                  limit: int = 100) -> List[Dict]:
        """
        Get alerts from audit database
        
        Args:
            start_time: Start timestamp
            end_time: End timestamp
            alert_type: Filter by alert type
            acknowledged: Filter by acknowledgment status
            limit: Maximum number of records
            
        Returns:
            List of alert dictionaries
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM alerts WHERE 1=1"
            params = []
            
            if start_time is not None:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time is not None:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            if alert_type is not None:
                query += " AND alert_type = ?"
                params.append(alert_type)
            
            if acknowledged is not None:
                query += " AND acknowledged = ?"
                params.append(1 if acknowledged else 0)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                alert = dict(row)
                alert['acknowledged'] = bool(alert['acknowledged'])
                results.append(alert)
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to get alerts: {e}")
            return []
    
    def get_loop_detections(self,
                           start_time: Optional[float] = None,
                           end_time: Optional[float] = None,
                           pid: Optional[int] = None,
                           min_confidence: float = 0.0,
                           limit: int = 100) -> List[Dict]:
        """
        Get loop detections from audit database
        
        Args:
            start_time: Start timestamp
            end_time: End timestamp
            pid: Filter by process ID
            min_confidence: Minimum confidence threshold
            limit: Maximum number of records
            
        Returns:
            List of loop detection dictionaries
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM loop_detections WHERE 1=1"
            params = []
            
            if start_time is not None:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time is not None:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            if pid is not None:
                query += " AND pid = ?"
                params.append(pid)
            
            if min_confidence > 0.0:
                query += " AND confidence >= ?"
                params.append(min_confidence)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append(dict(row))
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to get loop detections: {e}")
            return []
    
    def get_system_events(self,
                         start_time: Optional[float] = None,
                         end_time: Optional[float] = None,
                         event_type: Optional[str] = None,
                         severity: Optional[str] = None,
                         limit: int = 100) -> List[Dict]:
        """
        Get system events from audit database
        
        Args:
            start_time: Start timestamp
            end_time: End timestamp
            event_type: Filter by event type
            severity: Filter by severity
            limit: Maximum number of records
            
        Returns:
            List of system event dictionaries
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM system_events WHERE 1=1"
            params = []
            
            if start_time is not None:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time is not None:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            if event_type is not None:
                query += " AND event_type = ?"
                params.append(event_type)
            
            if severity is not None:
                query += " AND severity = ?"
                params.append(severity)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append(dict(row))
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to get system events: {e}")
            return []
    
    def acknowledge_alert(self, alert_id: int) -> bool:
        """
        Acknowledge an alert
        
        Args:
            alert_id: ID of alert to acknowledge
            
        Returns:
            True if successful
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE alerts SET acknowledged = 1 WHERE id = ?",
                (alert_id,)
            )
            
            conn.commit()
            rows_affected = cursor.rowcount
            conn.close()
            
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            return False
    
    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get audit statistics for the last N hours
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with statistics
        """
        try:
            cutoff_time = datetime.now().timestamp() - (hours * 3600)
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Process metrics stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_samples,
                    AVG(cpu_usage) as avg_cpu,
                    MAX(cpu_usage) as max_cpu,
                    AVG(memory_usage) as avg_memory,
                    MAX(memory_usage) as max_memory,
                    COUNT(DISTINCT pid) as unique_processes
                FROM process_metrics 
                WHERE timestamp >= ?
            """, (cutoff_time,))
            
            process_stats = dict(zip(
                ['total_samples', 'avg_cpu', 'max_cpu', 'avg_memory', 'max_memory', 'unique_processes'],
                cursor.fetchone()
            ))
            
            # Alerts stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_alerts,
                    COUNT(CASE WHEN acknowledged = 1 THEN 1 END) as acknowledged_alerts,
                    alert_type,
                    COUNT(*) as count
                FROM alerts 
                WHERE timestamp >= ?
                GROUP BY alert_type
            """, (cutoff_time,))
            
            alert_stats = {}
            for row in cursor.fetchall():
                alert_type, count = row[2], row[3]
                alert_stats[alert_type] = count
            
            # Loop detections stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_loops,
                    AVG(confidence) as avg_confidence,
                    MAX(confidence) as max_confidence
                FROM loop_detections 
                WHERE timestamp >= ?
            """, (cutoff_time,))
            
            loop_stats = dict(zip(
                ['total_loops', 'avg_confidence', 'max_confidence'],
                cursor.fetchone()
            ))
            
            conn.close()
            
            return {
                'time_range_hours': hours,
                'process_metrics': process_stats,
                'alerts': alert_stats,
                'loop_detections': loop_stats,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
    
    def export_data(self, 
                   format: str = "json",
                   start_time: Optional[float] = None,
                   end_time: Optional[float] = None,
                   data_types: List[str] = None) -> Optional[str]:
        """
        Export audit data to file
        
        Args:
            format: Export format ('json' or 'csv')
            start_time: Start timestamp
            end_time: End timestamp
            data_types: List of data types to export ['process', 'alerts', 'loops', 'events']
            
        Returns:
            Path to exported file, or None if failed
        """
        try:
            if data_types is None:
                data_types = ['process', 'alerts', 'loops', 'events']
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir = Path("./exports")
            export_dir.mkdir(exist_ok=True)
            
            export_file = export_dir / f"aetheros_audit_{timestamp}.{format}"
            
            data = {
                'export_info': {
                    'timestamp': timestamp,
                    'start_time': start_time,
                    'end_time': end_time,
                    'data_types': data_types,
                    'format': format
                },
                'data': {}
            }
            
            if 'process' in data_types:
                data['data']['process_metrics'] = self.get_process_metrics(
                    start_time, end_time, limit=10000
                )
            
            if 'alerts' in data_types:
                data['data']['alerts'] = self.get_alerts(
                    start_time, end_time, limit=1000
                )
            
            if 'loops' in data_types:
                data['data']['loop_detections'] = self.get_loop_detections(
                    start_time, end_time, limit=1000
                )
            
            if 'events' in data_types:
                data['data']['system_events'] = self.get_system_events(
                    start_time, end_time, limit=1000
                )
            
            if format.lower() == 'json':
                with open(export_file, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
            elif format.lower() == 'csv':
                # For CSV, we'd need to flatten the data - simplified for now
                import csv
                with open(export_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Data Type', 'Record Count'])
                    for data_type in data_types:
                        count = len(data['data'].get(f'{data_type}s' if data_type != 'process' else 'process_metrics', []))
                        writer.writerow([data_type, count])
            else:
                logger.error(f"Unsupported export format: {format}")
                return None
            
            logger.info(f"Exported audit data to {export_file}")
            return str(export_file)
            
        except Exception as e:
            logger.error(f"Failed to export data: {e}")
            return None