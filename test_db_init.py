import sys
sys.path.insert(0, '/mnt/c/Users/PC/Documents/Default Project/AetherOS/auditor')
sys.path.insert(0, '/mnt/c/Users/PC/Documents/Default Project/AetherOS/controller/src')
from audit.viewer import AuditViewer

v = AuditViewer('./auditor/aetheros_audit.db')
print("DB ready")