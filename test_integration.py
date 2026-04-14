#!/usr/bin/env python3
"""
Integration test for Aether-OS system
Tests that all components can be imported and instantiated without errors
"""

import sys
import os
import traceback

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    # Test probe components (check if source directory has the expected files)
    probe_src_dir = 'aether-os/probe/src'
    probe_include_dir = 'aether-os/probe/include'
    
    required_probe_src = [
        'main.cpp',
        'process_monitor.cpp', 
        'loop_detector.cpp',
        'system_interceptor.cpp',
        'zmq_communicator.cpp'
    ]
    
    required_probe_include = [
        'process_monitor.h',
        'loop_detector.h', 
        'system_interceptor.h',
        'zmq_communicator.h'
    ]
    
    for f in required_probe_src:
        if not os.path.exists(os.path.join(probe_src_dir, f)):
            print(f"❌ Missing probe source file: {f}")
            return False
        else:
            print(f"✅ Found probe source file: {f}")
    
    for f in required_probe_include:
        if not os.path.exists(os.path.join(probe_include_dir, f)):
            print(f"❌ Missing probe header file: {f}")
            return False
        else:
            print(f"✅ Found probe header file: {f}")
    
    # Test auditor imports
    try:
        sys.path.append('aether-os/auditor/src')
        from auditor import Auditor
        print("✅ Auditor import successful")
    except Exception as e:
        print(f"❌ Auditor import failed: {e}")
        traceback.print_exc()
        return False
    
    # Test controller imports
    try:
        sys.path.append('aether-os/controller/src')
        from snapshots.manager import SnapshotManager
        from policies.manager import PolicyManager
        from audit.viewer import AuditViewer
        print("✅ Controller manager imports successful")
    except Exception as e:
        print(f"❌ Controller manager imports failed: {e}")
        traceback.print_exc()
        return False
    
    # Test that controller can be instantiated (without running UI)
    try:
        # We'll test the managers directly
        snapshot_mgr = SnapshotManager()
        policy_mgr = PolicyManager()
        audit_viewer = AuditViewer()
        print("✅ Controller manager instantiation successful")
    except Exception as e:
        print(f"❌ Controller manager instantiation failed: {e}")
        traceback.print_exc()
        return False
        
    return True

def test_basic_functionality():
    """Test basic functionality of each component"""
    print("\nTesting basic functionality...")
    
    # Test SnapshotManager
    try:
        sys.path.append('aether-os/controller/src')
        from snapshots.manager import SnapshotManager
        snapshot_mgr = SnapshotManager("./test_snapshots")
        # Test listing snapshots (should be empty initially)
        snapshots = snapshot_mgr.list_snapshots()
        assert isinstance(snapshots, list)
        print("✅ SnapshotManager basic functionality OK")
        # Cleanup
        import shutil
        if os.path.exists("./test_snapshots"):
            shutil.rmtree("./test_snapshots")
    except Exception as e:
        print(f"❌ SnapshotManager test failed: {e}")
        traceback.print_exc()
        return False
    
    # Test PolicyManager
    try:
        from policies.manager import PolicyManager
        policy_mgr = PolicyManager("./test_policies")
        # Test getting a policy
        policy = policy_mgr.get_policy('loop_detection')
        assert isinstance(policy, dict)
        assert 'enabled' in policy
        print("✅ PolicyManager basic functionality OK")
        # Cleanup
        if os.path.exists("./test_policies"):
            shutil.rmtree("./test_policies")
    except Exception as e:
        print(f"❌ PolicyManager test failed: {e}")
        traceback.print_exc()
        return False
    
    # Test AuditViewer (will create demo DB if needed)
    try:
        from audit.viewer import AuditViewer
        audit_viewer = AuditViewer("./test_audit.db")
        # Test getting stats (should work even with empty DB)
        stats = audit_viewer.get_statistics(hours=24)
        assert isinstance(stats, dict)
        print("✅ AuditViewer basic functionality OK")
        # Cleanup
        if os.path.exists("./test_audit.db"):
            os.remove("./test_audit.db")
    except Exception as e:
        print(f"❌ AuditViewer test failed: {e}")
        traceback.print_exc()
        return False
        
    return True

def main():
    print("=== Aether-OS Integration Test ===")
    
    if not test_imports():
        print("\n❌ Import tests failed")
        return 1
        
    if not test_basic_functionality():
        print("\n❌ Basic functionality tests failed")
        return 1
        
    print("\n✅ All integration tests passed!")
    print("The Aether-OS system is ready for use.")
    return 0

if __name__ == "__main__":
    sys.exit(main())