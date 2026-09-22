import time
import os
print("PID: " + str(os.getpid()))
while True:
    for i in range(1000000):
        _ = i * i
    time.sleep(0.1)