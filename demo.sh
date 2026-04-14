#!/bin/bash
echo 'Starting Aether-OS demonstration...'

# Start probe monitoring self PID
cd probe/build && ./aetheros-probe 3246 &
PROBE_PID=

# Start auditor
cd ../auditor && python3 src/auditor.py --paths . --zmq-endpoint tcp://localhost:5555 &
AUDITOR_PID=

# Start controller
cd ../controller && python3 src/controller.py &
CONTROLLER_PID=

echo 'All components started!'
echo 'Probe PID: '
echo 'Auditor PID: '
echo 'Controller PID: '

echo 'Press Ctrl+C to stop all components'
wait
