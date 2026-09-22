import sys
sys.path.insert(0, '/mnt/c/Users/PC/Documents/Default Project/AetherOS/auditor')
sys.path.insert(0, '/mnt/c/Users/PC/Documents/Default Project/AetherOS/controller/src')
from audit.viewer import AuditViewer

v = AuditViewer('./auditor/aetheros_audit.db')
metrics = v.get_process_metrics(limit=5)
alerts = v.get_alerts(limit=5)
loops = v.get_loop_detections(limit=5)
print('=== Process Metrics ===')
for m in metrics:
    print(f'  PID: {m["pid"]}, CPU: {m["cpu_usage"]:.2f}%, MEM: {m["memory_usage"]}KB, Disk R/W: {m["disk_read"]}/{m["disk_write"]}KB')
print('=== Alerts ===')
for a in alerts:
    print(f'  Type: {a["alert_type"]}, Confidence: {a["confidence"]}, PID: {a["pid"]}, Details: {a["details"][:50]}')
print('=== Loop Detections ===')
for l in loops:
    print(f'  PID: {l["pid"]}, Confidence: {l["confidence"]}, CPU: {l["cpu_usage"]:.2f}%, Samples: {l["similar_samples"]}')