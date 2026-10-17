#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== Post-cleanup verification ==="

echo "1. Auditor import:"
cd "$SCRIPT_DIR/auditor"
python3 -c 'from auditor import Auditor; a = Auditor(); print("   [OK] Auditor imports and instantiates")'

echo "2. Controller managers:"
cd "$SCRIPT_DIR/controller"
python3 -c "
import sys
sys.path.insert(0, 'src')
from snapshots.manager import SnapshotManager
from policies.manager import PolicyManager
from audit.viewer import AuditViewer
SnapshotManager()
PolicyManager()
AuditViewer()
print('   [OK] All Controller managers import and instantiate')
"

echo "3. Probe binary:"
if [ -f "$SCRIPT_DIR/probe/build/aetheros-probe" ]; then
    echo "   [OK] Probe binary present"
else
    echo "   [FAIL] Probe binary missing"
fi

echo "4. Auditor CLI flags:"
cd "$SCRIPT_DIR/auditor"
python3 auditor.py --help | grep -E "zmq|log-file|probe-input" | head -5

echo ""
echo "=== ALL VERIFICATIONS DONE ==="