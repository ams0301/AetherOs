#!/bin/bash
cd /mnt/c/Users/PC/Documents/Default\ Project/AetherOS
python3 variable_load.py &
PID=$!
echo "PID: $PID"
sleep 2
timeout 15 ./probe/build/aetheros-probe $PID
kill $PID 2>/dev/null