#!/bin/bash
cd /mnt/c/Users/PC/Documents/Default\ Project/AetherOS
rm -f auditor/aetheros_audit.db

# Start auditor in ZMQ mode
cd auditor
timeout 25 python3 auditor.py --zmq --db-path ./aetheros_audit.db &
AUDITOR_PID=$!
echo "Auditor PID: $AUDITOR_PID"
sleep 3

# Run probe monitoring self (bash process)
cd ../probe/build
timeout 15 ./aetheros-probe $$

sleep 2
kill $AUDITOR_PID 2>/dev/null

echo "=== Checking audit database ==="
cd ../../
python3 test_db_init.py
python3 -c "
import sys
sys.path.insert(0, 'auditor')
sys.path.insert(0, 'controller/src')
from audit.viewer import AuditViewer
v = AuditViewer('./auditor/aetheros_audit.db')
print('Process metrics:', len(v.get_process_metrics(limit=100)))
print('Alerts:', len(v.get_alerts(limit=100)))
print('Loop detections:', len(v.get_loop_detections(limit=100)))
print('System events:', len(v.get_system_events(limit=100)))
"