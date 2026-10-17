#!/bin/bash
echo 'Starting Aether-OS demonstration...'

# Start probe monitoring self PID
cd probe/build && ./aetheros-probe $$ &
PROBE_PID=$!

# Start auditor (subscribes to the probe's ZMQ stream)
cd ../auditor && python3 auditor.py --zmq &
AUDITOR_PID=$!

# Start controller
cd ../controller/src && python3 controller.py &
CONTROLLER_PID=$!

echo 'All components started!'
echo "Probe PID: $PROBE_PID"
echo "Auditor PID: $AUDITOR_PID"
echo "Controller PID: $CONTROLLER_PID"

echo 'Press Ctrl+C to stop all components'
wait