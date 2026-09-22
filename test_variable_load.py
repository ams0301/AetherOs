#!/usr/bin/env python3
import time
import random
import os

# This script creates variable CPU load
while True:
    # Do some CPU work
    for i in range(100000):
        _ = i * i
    # Sleep randomly
    time.sleep(random.uniform(1, 3))