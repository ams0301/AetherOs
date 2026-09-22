import sys
sys.path.insert(0, '/mnt/c/Users/PC/Documents/Default Project/AetherOS/auditor')
sys.path.insert(0, '/mnt/c/Users/PC/Documents/Default Project/AetherOS/controller/src')

from auditor import AuditViewer

v = AuditViewer('./aetheros_audit.db')
print('DB initialized successfully')

# Test insert
import time
v.insert_process_metrics(time.time(), 1234, 'test_process', 50.0, 102400, 100, 200)
v.insert_alert(time.time(), 'test_alert', 0.9, 1234, 'Test alert details')
v.insert_loop_detection(time.time(), 1234, 0.85, 50.0, 102400, 5)

print('Test inserts completed')

# Verify
metrics = v.get_process_metrics(limit=10)
alerts = v.get_alerts(limit=10)
loops = v.get_loop_detections(limit=10)

print(f'Metrics: {len(metrics)}')
print(f'Alerts: {len(alerts)}')
print(f'Loops: {len(loops)}')