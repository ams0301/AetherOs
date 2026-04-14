"""
Snapshot Manager for Aether-OS Controller
Handles creation, listing, and restoration of process snapshots
"""

import os
import json
import tarfile
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class SnapshotManager:
    def __init__(self, snapshot_dir: str = "./snapshots"):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(exist_ok=True)
        self.metadata_file = self.snapshot_dir / "metadata.json"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load snapshot metadata from file"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load snapshot metadata: {e}")
                return {}
        return {}
    
    def _save_metadata(self):
        """Save snapshot metadata to file"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save snapshot metadata: {e}")
    
    def create_snapshot(self, pid: int, description: str = "") -> Optional[str]:
        """
        Create a snapshot of a process
        
        Args:
            pid: Process ID to snapshot
            description: Optional description for the snapshot
            
        Returns:
            Snapshot ID if successful, None otherwise
        """
        try:
            import psutil
            
            # Check if process exists
            try:
                process = psutil.Process(pid)
            except psutil.NoSuchProcess:
                logger.error(f"Process {pid} does not exist")
                return None
            
            # Generate snapshot ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_id = f"snapshot_{pid}_{timestamp}"
            snapshot_path = self.snapshot_dir / snapshot_id
            snapshot_path.mkdir()
            
            # Collect process information
            snapshot_data = {
                'pid': pid,
                'timestamp': timestamp,
                'description': description,
                'process_info': self._collect_process_info(process),
                'memory_map': self._collect_memory_map(process),
                'open_files': self._collect_open_files(process),
                'connections': self._collect_connections(process),
                'environ': dict(process.environ()),
                'cwd': process.cwd(),
                'status': process.status(),
                'name': process.name(),
                'cmdline': process.cmdline(),
                'create_time': process.create_time(),
                'parent_ppid': process.ppid(),
            }
            
            # Save snapshot data
            data_file = snapshot_path / "data.json"
            with open(data_file, 'w') as f:
                json.dump(snapshot_data, f, indent=2)
            
            # Try to create a core dump if possible (requires permissions)
            try:
                core_file = snapshot_path / "core.dump"
                # Note: Actual core dumping requires gdb or similar and proper permissions
                # This is a placeholder for the concept
                with open(core_file, 'w') as f:
                    f.write(f"# Core dump placeholder for PID {pid}\n")
                    f.write(f"# Generated at {timestamp}\n")
                    f.write(f"# In a real implementation, this would contain actual process memory\n")
            except Exception as e:
                logger.warning(f"Could not create core dump: {e}")
            
            # Create archive
            archive_path = self.snapshot_dir / f"{snapshot_id}.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(snapshot_path, arcname=snapshot_id)
            
            # Clean up temporary directory
            shutil.rmtree(snapshot_path)
            
            # Update metadata
            self.metadata[snapshot_id] = {
                'pid': pid,
                'timestamp': timestamp,
                'description': description,
                'archive_path': str(archive_path),
                'created_at': datetime.now().isoformat(),
                'size': archive_path.stat().st_size
            }
            self._save_metadata()
            
            logger.info(f"Created snapshot {snapshot_id} for PID {pid}")
            return snapshot_id
            
        except Exception as e:
            logger.error(f"Failed to create snapshot for PID {pid}: {e}")
            return None
    
    def _collect_process_info(self, process) -> Dict:
        """Collect basic process information"""
        try:
            return {
                'pid': process.pid,
                'name': process.name(),
                'exe': process.exe(),
                'cmdline': process.cmdline(),
                'status': process.status(),
                'create_time': process.create_time(),
                'parent_ppid': process.ppid(),
                'num_threads': process.num_threads(),
                'num_fds': process.num_fds() if hasattr(process, 'num_fds') else 0,
                'cpu_percent': process.cpu_percent(),
                'memory_info': process.memory_info()._asdict(),
                'memory_percent': process.memory_percent(),
            }
        except Exception as e:
            logger.debug(f"Could not collect full process info: {e}")
            return {}
    
    def _collect_memory_map(self, process) -> List[Dict]:
        """Collect process memory map"""
        try:
            maps = []
            for mmap in process.memory_maps():
                maps.append({
                    'path': mmap.path,
                    'rss': mmap.rss,
                    'size': mmap.size,
                    'pss': mmap.pss,
                    'shared_clean': mmap.shared_clean,
                    'shared_dirty': mmap.shared_dirty,
                    'private_clean': mmap.private_clean,
                    'private_dirty': mmap.private_dirty,
                    'referenced': mmap.referenced,
                    'anonymous': mmap.anonymous,
                    'swap': mmap.swap,
                })
            return maps
        except Exception as e:
            logger.debug(f"Could not collect memory map: {e}")
            return []
    
    def _collect_open_files(self, process) -> List[Dict]:
        """Collect open file information"""
        try:
            files = []
            for file in process.open_files():
                files.append({
                    'path': file.path,
                    'fd': file.fd,
                    'position': file.position,
                    'mode': file.mode,
                    'flags': file.flags,
                })
            return files
        except Exception as e:
            logger.debug(f"Could not collect open files: {e}")
            return []
    
    def _collect_connections(self, process) -> List[Dict]:
        """Collect network connection information"""
        try:
            conns = []
            for conn in process.connections():
                conns.append({
                    'fd': conn.fd,
                    'family': conn.family.name if hasattr(conn.family, 'name') else str(conn.family),
                    'type': conn.type.name if hasattr(conn.type, 'name') else str(conn.type),
                    'laddr': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                    'raddr': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                    'status': conn.status,
                })
            return conns
        except Exception as e:
            logger.debug(f"Could not collect connections: {e}")
            return []
    
    def list_snapshots(self) -> List[Dict]:
        """List all available snapshots"""
        snapshots = []
        for snapshot_id, metadata in self.metadata.items():
            snapshot_info = metadata.copy()
            snapshot_info['id'] = snapshot_id
            snapshots.append(snapshot_info)
        
        # Sort by creation time (newest first)
        snapshots.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return snapshots
    
    def restore_snapshot(self, snapshot_id: str, target_pid: Optional[int] = None) -> bool:
        """
        Restore a snapshot (conceptual - actual restoration requires ptrace/gdb)
        
        Args:
            snapshot_id: ID of snapshot to restore
            target_pid: Optional target PID to restore into (if None, creates new process)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if snapshot_id not in self.metadata:
                logger.error(f"Snapshot {snapshot_id} not found")
                return False
            
            metadata = self.metadata[snapshot_id]
            archive_path = Path(metadata['archive_path'])
            
            if not archive_path.exists():
                logger.error(f"Snapshot archive not found: {archive_path}")
                return False
            
            # Extract snapshot
            with tempfile.TemporaryDirectory() as temp_dir:
                snapshot_path = Path(temp_dir) / "snapshot"
                with tarfile.open(archive_path, "r:gz") as tar:
                    tar.extractall(path=temp_dir)
                
                # Load snapshot data
                data_file = snapshot_path / "data.json"
                with open(data_file, 'r') as f:
                    snapshot_data = json.load(f)
                
                logger.info(f"Restored snapshot {snapshot_id} for PID {snapshot_data['pid']}")
                logger.info(f"Original command: {' '.join(snapshot_data['cmdline'])}")
                logger.info(f"Snapshot created: {snapshot_data['timestamp']}")
                
                # In a real implementation, we would:
                # 1. Use ptrace to attach to target process (or create new one)
                # 2. Restore memory map from snapshot
                # 3. Restore registers and CPU state
                # 4. Resume process execution
                #
                # For now, we provide the information for manual restoration
                print(f"\n=== SNAPSHOT RESTORATION INFO ===")
                print(f"Snapshot ID: {snapshot_id}")
                print(f"Original PID: {snapshot_data['pid']}")
                print(f"Command: {' '.join(snapshot_data['cmdline'])}")
                print(f"Working Directory: {snapshot_data['cwd']}")
                print(f"Environment Variables: {len(snapshot_data['environ'])} variables")
                print(f"Open Files: {len(snapshot_data['open_files'])} files")
                print(f"Memory Regions: {len(snapshot_data['memory_map'])} regions")
                print(f"Network Connections: {len(snapshot_data['connections'])} connections")
                print(f"To manually restore, you would need to:")
                print(f"  1. Start process: {' '.join(snapshot_data['cmdline'])}")
                print(f"  2. Set working directory: {snapshot_data['cwd']}")
                print(f"  3. Apply environment variables")
                print(f"  4. Use debugger to restore memory state")
                print(f"===============================\n")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to restore snapshot {snapshot_id}: {e}")
            return False
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot"""
        try:
            if snapshot_id not in self.metadata:
                logger.error(f"Snapshot {snapshot_id} not found")
                return False
            
            metadata = self.metadata[snapshot_id]
            archive_path = Path(metadata['archive_path'])
            
            if archive_path.exists():
                archive_path.unlink()
            
            del self.metadata[snapshot_id]
            self._save_metadata()
            
            logger.info(f"Deleted snapshot {snapshot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete snapshot {snapshot_id}: {e}")
            return False
    
    def get_snapshot_details(self, snapshot_id: str) -> Optional[Dict]:
        """Get detailed information about a snapshot"""
        if snapshot_id not in self.metadata:
            return None
        
        metadata = self.metadata[snapshot_id].copy()
        metadata['id'] = snapshot_id
        
        # Load full data if needed
        archive_path = Path(metadata['archive_path'])
        if archive_path.exists():
            with tempfile.TemporaryDirectory() as temp_dir:
                snapshot_path = Path(temp_dir) / "snapshot"
                with tarfile.open(archive_path, "r:gz") as tar:
                    tar.extractall(path=temp_dir)
                
                data_file = snapshot_path / "data.json"
                if data_file.exists():
                    with open(data_file, 'r') as f:
                        full_data = json.load(f)
                    metadata['full_data'] = full_data
        
        return metadata