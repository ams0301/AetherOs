#!/usr/bin/env python3
"""
Test process to generate activity for Aether-OS probe monitoring
"""

import time
import sys
import random

def worker_task():
    """Simulate some work that creates measurable activity"""
    counter = 0
    while counter < 100:  # Run for a limited time
        # Simulate some CPU work
        total = 0
        for i in range(10000):
            total += i * i
        
        # Simulate some memory allocation
        data = [random.random() for _ in range(1000)]
        
        # Small sleep to yield CPU
        time.sleep(0.1)
        
        counter += 1
        if counter % 10 == 0:
            print(f"Worker step {counter}/100")
    
    print("Worker task completed")

if __name__ == "__main__":
    print("Starting test process...")
    print(f"Process ID: {__import__('os').getpid()}")
    worker_task()