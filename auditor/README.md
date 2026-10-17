# Auditor Component

Live analysis, detection, and audit persistence layer written in Python.

## Responsibilities
- Subscribe to the Probe's live ZeroMQ metric/alert stream
- Tail agent log files and extract executed commands
- Detect loops at two layers: syntactic (repeated command sequences) and semantic (repeated error patterns)
- Persist all metrics, alerts, loop detections, and system events to the SQLite audit database
- Communicate findings to the Controller for visualization

## Key Features
- **ZMQ subscription mode** (`--zmq`): live pipeline from Probe, writes everything to SQLite
- **Log tail mode** (`--log-file`): follows an agent log and detects repeated `[exec]` command windows
- **Stdin mode** (`--probe-input`): consumes JSON alert lines for testing/gluing
- Syntactic loop detection: same N-command window repeating M times
- Semantic analysis: regex-based error recognition (error/fail/timeout/denied patterns)
- Error-signature normalization: digits and paths masked so "same failure, different details" is caught
- Alert enrichment with semantic context
- Configurable window size and alert threshold

## Usage
```bash
# Live mode: subscribe to the probe's ZMQ stream and persist to the audit DB
python3 auditor.py --zmq

# Custom endpoint and database path
python3 auditor.py --zmq --zmq-endpoint tcp://localhost:5555 --db-path ./aetheros_audit.db

# Log tail mode
python3 auditor.py --log-file /path/to/agent.log --window 5 --threshold 3

# Stdin mode
some_producer | python3 auditor.py --probe-input
```

## Dependencies
- Python 3.8+
- pyzmq (ZeroMQ communication)
- watchdog (file system monitoring)
- loguru (enhanced logging)
- Python standard library: `sqlite3`, `re`, `json`, `collections`, `threading`

> **Note:** Earlier versions of this doc listed pandas/numpy/scikit-learn for an Isolation-Forest-based
> detector that was never implemented. Those dependencies were removed — the actual detection is the
> regex + repeated-state analysis described above. See the root `INTERVIEW_GUIDE.md` for details.

## Audit Database Schema
Four indexed tables (created automatically):
- `process_metrics` — timestamped CPU/memory/disk samples per PID
- `alerts` — alert type, confidence, PID, details, acknowledged flag
- `loop_detections` — PID, confidence, CPU/memory at detection, sample count
- `system_events` — event type, source, description, severity
