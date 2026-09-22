#!/usr/bin/env python3
import time
import random
import os

print(f"PID: {os.getpid()}")
# Variable CPU load: sometimes burn, sometimes sleep
while True:
    # 30% chance to burn CPU
    if random.random() < 0.3:
        for i in range(500000):
            _ = i * i
    else:
        time.sleep(random.uniform(0.5, 2.0))