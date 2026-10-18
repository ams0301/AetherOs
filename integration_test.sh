#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
rm -f auditor/aetheros_audit.db

cd auditor
timeout 30 python3 auditor.py --zmq --db-path ./aetheros_audit.db > /tmp/auditor_e2e.log 2>&1 &
AUDITOR_PID=$!
sleep 3

cd "$SCRIPT_DIR/probe/build"
gcc -std=c11 -O2 "$SCRIPT_DIR/probe/tests/spin_target.c" -o /tmp/aetheros_spin
/tmp/aetheros_spin &
BURNER_PID=$!
echo "CPU spinner PID: $BURNER_PID"
sleep 1

cd "$SCRIPT_DIR/probe/build"
timeout 12 ./aetheros-probe $BURNER_PID 2>&1 | grep -E "LOOP DETECTED|Samples:" | head -12

kill $BURNER_PID $AUDITOR_PID 2>/dev/null
wait $BURNER_PID $AUDITOR_PID 2>/dev/null

echo "=== Audit database after run ==="
cd "$SCRIPT_DIR"
python3 - <<'EOF'
import sys
sys.path.insert(0, 'auditor')
sys.path.insert(0, 'controller/src')
from audit.viewer import AuditViewer
v = AuditViewer('./auditor/aetheros_audit.db')
metrics = len(v.get_process_metrics(limit=1000))
alerts = len(v.get_alerts(limit=1000))
loops = len(v.get_loop_detections(limit=1000))
print(f"process_metrics rows: {metrics}")
print(f"alerts rows:          {alerts}")
print(f"loop_detections rows: {loops}")
if metrics > 0 and loops > 0:
    print("E2E PASS: metrics flowed and active loop detected + persisted")
    sys.exit(0)
print("E2E FAIL")
sys.exit(1)
EOF