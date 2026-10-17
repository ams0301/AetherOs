# Aether-OS: Complete Interview & Deep-Dive Guide

> **How to use this document:** Read Part 1–2 the night before an interview. Read Part 3–5 for technical rounds. Read Part 6 (Q&A Bank) out loud the morning of. The Cheat Sheet at the bottom has every number, name, and formula you should memorize.

---

## Table of Contents

- **Part 1: The Pitch** (30-second and 2-minute versions)
- **Part 2: Explaining It to a Non-Technical Person** (analogies, zero jargon)
- **Part 3: The Architecture** (components, data flow, why every decision was made)
- **Part 4: Deep Dives** (every feature, every algorithm, every file)
- **Part 5: The Bugs I Found and Fixed** (your best interview stories)
- **Part 6: Interview Q&A Bank** (50+ questions with answers)
- **Part 7: Honest Limitations** (what to say when pressed)
- **Part 8: Cheat Sheet** (numbers and formulas to memorize)
- **Part 9: Glossary** (every term, in plain English)

---

# PART 1: THE PITCH

## The 30-Second Version (memorize this)

> "Aether-OS is a monitoring and safety system for AI agents. When an AI agent runs autonomously, it can get stuck in infinite reasoning loops, exhaust CPU and memory, or repeat failing actions forever. Aether-OS watches those processes in real time, detects when behavior becomes repetitive or abnormal, records everything to an audit database, and gives a human operator a dashboard to pause, resume, or kill the runaway process. It's built as three decoupled components — a C++ probe that collects low-level process metrics, a Python auditor that analyzes and stores them, and a Python controller that provides the operator dashboard — all connected by ZeroMQ pub/sub messaging."

## The 2-Minute Version (for "tell me about your project")

> "The problem: AI agents that run autonomously — coding assistants, automation agents — sometimes enter infinite loops. They burn CPU, spin forever, or repeat the same failing command hundreds of times. There was no good way to detect this happening at the OS level, intervene safely, and keep an audit trail of what happened.
>
> My system, Aether-OS, solves this with three components. The **Probe** is written in C++20 because it reads process data directly from the Linux `/proc` filesystem every 500 milliseconds — CPU time, memory, disk I/O — and runs a sliding-window similarity algorithm to detect when a process's behavior becomes repetitive, which is the signature of a loop. The **Auditor** is a Python service that subscribes to the Probe's live ZeroMQ stream, applies a second layer of analysis — including semantic checks like 'are the last N log lines all errors?' — and writes everything into a SQLite audit database. The **Controller** is a terminal-based dashboard where a human can see live metrics, browse the audit trail, manage policies, take snapshots, and send pause/resume/terminate signals to any process.
>
> The interesting engineering problems were at the systems level. For example, the syscall interception uses `ptrace`, and Linux requires that *all* ptrace calls on a tracee come from the same thread — a bug in the original code attached on the main thread but polled from a worker thread, causing false 'process no longer exists' errors. I found and fixed that, along with a CPU calculation formula that only worked by coincidence on 100Hz x86 systems, a cache that was never populated so CPU always read 0%, and a loop detector whose fixed normalization constants made it fire false positives on nearly every light workload — I made normalization adaptive per-process instead.
>
> End result: a working end-to-end pipeline — probe detects, auditor records, controller displays — verified by integration tests where I watched real metrics flow through ZMQ into the database."

---

# PART 2: EXPLAINING IT TO A NON-TECHNICAL PERSON

Use this for: mixed panels, PM interviews, explaining to family, or as a warm-up before diving deep.

## The Analogy: A Hospital Intensive Care Unit

Imagine an AI agent is a **patient** in a hospital. The patient was told to do a job — say, organize a warehouse — and left alone to do it. Most of the time that's fine. But sometimes something goes wrong:

- The patient starts **walking in circles** (an infinite loop)
- The patient's **heart rate spikes** and never comes down (CPU exhaustion)
- The patient keeps **repeating the same failed action** — trying the same locked door 500 times (repeated errors)

Aether-OS is the **ICU monitoring system** for that patient:

| Real-world hospital | Aether-OS equivalent | What it is |
|---|---|---|
| Heart rate monitor on the patient's chest | **Probe** | A tiny program glued to the AI process that reads its vital signs — CPU, memory, disk usage — twice every second |
| The nurse who watches the monitors and says "this looks wrong" | **Auditor** | A program that receives the vital signs over the network, applies rules like "has this pattern repeated for 10 seconds?", and writes everything down in official medical records |
| The medical chart / patient file | **Audit database** | A permanent record of every vital sign and every alarm, so you can reconstruct exactly what happened, when, and why |
| The doctor's control panel with the "sedate patient" button | **Controller** | A dashboard where a human can see everything live and press buttons to pause, resume, or stop the AI process |
| The nurses' station intercom system | **ZeroMQ** | The messaging system the three components use to talk to each other, like hospital staff calling each other over the PA |

**The key sentence for a non-technical person:**

> "It's a smoke detector, flight data recorder, and emergency brake — all three — for AI programs that run on their own."

- **Smoke detector** = it notices trouble early (loop detection)
- **Flight data recorder** = it keeps a permanent record of what happened (SQLite audit trail)
- **Emergency brake** = a human can stop the runaway program safely (pause/terminate controls)

## Why would anyone need this?

When you ask an AI to do a task without supervising it ("autonomously"), the AI might:
1. Get stuck repeating the same thought pattern forever (wasting electricity/compute money)
2. Fill up memory until the machine crashes
3. Repeat an action that fails, forever — like retrying a network request in a tight loop

Companies running AI agents on real servers lose real money when this happens. Aether-OS watches for exactly these failure modes.

---

# PART 3: THE ARCHITECTURE

## The Diagram (draw this on any whiteboard)

```
                        ┌──────────────────────────┐
                        │   TARGET PROCESS (any    │
                        │   AI agent / program)    │
                        └────────────┬─────────────┘
                                     │ (read-only)
                                     ▼
┌─────────────────────────────────────────────────────────┐
│                      PROBE (C++20)                      │
│                                                         │
│  ProcessMonitor ──► reads /proc/<pid>/stat, statm, io   │
│        │                                                │
│        ▼                                                │
│  LoopDetector ──► sliding-window similarity check      │
│        │                                                │
│  SystemInterceptor ──► ptrace syscall watching (opt.)  │
│        │                                                │
│        ▼                                                │
│  ZmqCommunicator ──► PUB socket tcp://*:5555            │
└────────────────────────┬────────────────────────────────┘
                         │  JSON messages (pub/sub)
            ┌────────────┴────────────┐
            ▼                         ▼
┌───────────────────────┐   ┌──────────────────────────┐
│   AUDITOR (Python)    │   │   CONTROLLER (Python)     │
│                       │   │                          │
│  ZMQ SUB ──► live     │   │  ZMQ SUB ──► live alerts │
│  Log tail ──► errors  │   │  Textual TUI dashboard   │
│  Loop/enrich logic    │   │  Pause/Resume/Terminate  │
│  ▼                    │   │  Snapshots/Policies      │
│  SQLite audit DB ◄────┼───┤  Audit trail browser     │
└───────────────────────┘   └──────────────────────────┘
         │
         ▼  (Controller reads the same DB for history)
```

## The Three Components and Why Each Exists

### Why three separate components at all?

**Separation of concerns**, the same reason a kitchen has separate prep, cooking, and plating stations:

1. **Different lifecycles**: The probe must run constantly with near-zero overhead. The auditor might be restarted or run on another machine. The controller is only open when a human wants to look. If they were one program, restarting the dashboard would kill your monitoring.
2. **Different performance requirements**: The probe is performance-critical C++ touching the kernel's `/proc` interface. The auditor does string analysis and database writes — perfectly fine in Python. The controller renders a UI — Python again. One language for all three would mean either a slow probe or a painfully low-level dashboard.
3. **Independent scaling**: You can run 10 probes on 10 servers, all publishing to one central auditor. Pub/sub makes this trivial.
4. **Fault isolation**: If the auditor crashes, the probe keeps monitoring (messages just queue/drop harmlessly). If the controller crashes, nothing about monitoring changes. Each failure is contained.

### Why C++ for the Probe?

- It reads `/proc/<pid>/stat` and does timestamp math **every 500ms**. Doing this in C++ costs well under 1% of one CPU core.
- It optionally uses **ptrace** for syscall interception — a raw Linux kernel interface, natural territory for C++.
- Zero-copy, no garbage collector pauses, no interpreter startup — the probe is a long-running daemon and C++20 gives modern ergonomics (std::chrono, std::thread, std::atomic) without runtime overhead.

**Anticipated follow-up: "Isn't C++ overkill?"** — Answer: "The heavy lifting here is literally reading tiny procfs files and doing arithmetic, so yes, any language *could* do it. But the design goal was <1% overhead on the monitored machine, plus direct access to ptrace, and C++ guarantees both. If this were a script that ran once a minute, I'd have written it in Python."

### Why Python for the Auditor and Controller?

- **Auditor**: The work is parsing JSON, running regexes over log lines, and writing SQLite rows. Python's standard library covers all three. Development speed matters more than raw speed here — the auditor handles ~2 messages/second per probe, nowhere near Python's limits.
- **Controller**: The dashboard is built with **Textual**, a Python TUI framework (think "React for terminals"). Rapid UI iteration matters far more than performance for a human-facing dashboard.

### Why ZeroMQ for the messaging?

ZeroMQ is a lightweight messaging library — "sockets on steroids." The probe **publishes** (PUB socket); the auditor and controller **subscribe** (SUB sockets).

Why pub/sub instead of plain REST calls or a message queue like Kafka:

| Option | Why not |
|---|---|
| REST (HTTP) | Wrong shape: probe would need to know who's listening, handle retries, deal with HTTP overhead. We have one-way telemetry, not request/response. |
| Kafka/RabbitMQ | Requires running a broker process — an entire extra server dependency for a system that's often deployed on one box. ZeroMQ is brokerless: the probe binds a port, subscribers connect directly. |
| Raw TCP | We'd hand-roll framing, reconnection, and fan-out. ZeroMQ gives all three in ~10 lines. |
| **ZeroMQ pub/sub** | **Brokerless, one-to-many fan-out for free, drops messages instead of blocking when a subscriber is slow (exactly the behavior we want for telemetry), ~200-byte messages.** |

**The one-line justification:** "Telemetry is fire-and-forget; pub/sub models that perfectly, and ZeroMQ gives it to us without a broker process to babysit."

**Anticipated follow-up: "What's lost when a subscriber is slow?"** — ZeroMQ drops messages at the subscriber once the high-water mark (1000 messages, our `sndhwm`) is hit. For telemetry that's *correct*: stale samples are worthless; you want the newest state. For the alerts channel the same drop policy applies, which is acceptable because the probe also writes loop detections to the audit DB via the auditor — a durable path.

## The Message Contract

Every message on the wire is a tiny JSON object:

```json
{
  "type": "0",
  "timestamp": 1790065025846,
  "source_pid": 7215,
  "payload": { "cpu_usage": 3.2, "memory_kb": 3328, "disk_read_kb": 24, "disk_write_kb": 0 }
}
```

| type | Meaning | Payload contents |
|---|---|---|
| `"0"` | PROCESS_METRICS | cpu_usage, memory_kb, disk_read_kb, disk_write_kb |
| `"1"` | LOOP_DETECTED | confidence (0–1), details (human-readable string) |
| `"2"` | SYSTEM_EVENT | event_type, description |
| `"3"` | HEARTBEAT | empty (proof-of-life every 30s) |
| `"4"` | ERROR | error message text |

**Fun bug story embedded here** (covered fully in Part 5): the type was serialized as a *string* `"0"` but the auditor originally compared it as an *integer* `0` — so every message was silently ignored until I fixed the comparison and the payload handling (the payload arrived already-parsed by `json.loads` on the outer object, but the auditor tried to `json.loads` it *again*).

## End-to-End Data Flow (walk through this aloud)

1. **Probe starts**: takes a target PID as an argument (or monitors itself for demo). Binds a ZMQ PUB socket on `tcp://*:5555`. Optionally spawns the ptrace interceptor thread.
2. **Every 500ms**, the probe's `ProcessMonitor::getProcessInfo(pid)`:
   - Opens `/proc/<pid>/stat`, parses fields 14–17 (utime, stime, cutime, cstime — CPU time in clock ticks).
   - Compares against the **cached previous sample** for this PID, computes CPU%.
   - Opens `/proc/<pid>/statm`, reads field 2 (resident pages) → memory in KB.
   - Opens `/proc/<pid>/io`, reads `rchar:`/`wchar:` → cumulative disk I/O in KB.
   - Stores this sample in the cache for the next diff.
3. The sample is fed to the **LoopDetector** as a 4-dimensional feature vector (CPU, memory-MB, disk-read, disk-write). The detector keeps a circular window of the last 15 samples and asks: "how similar is the new sample to each of the previous ones?"
4. Similarity is computed on **normalized** features (so CPU% and disk-KB are comparable), using Euclidean distance + exponential decay: `similarity = exp(-distance/scale)`.
5. If enough previous samples are "similar enough" (≥ the match threshold), a **loop detection** is raised with a confidence score (the average similarity of the matches). The probe prints it, publishes it on ZMQ, and resets its window.
6. Regardless of detection, the probe **publishes every metric sample** on ZMQ (type `"0"`).
7. The **Auditor**, running `auditor.py --zmq`, receives the message on its SUB socket in a background thread:
   - Type `"0"` → INSERT a row into the `process_metrics` table (SQLite).
   - Type `"1"` → enrich with semantic context, INSERT rows into both `loop_detections` and `alerts`.
   - Type `"2"`/`"4"` → INSERT into `system_events`.
8. The **Controller** (Textual TUI) is also subscribed: it shows live metrics in a table and appends alerts as they arrive. When you open the Audit tab, it queries the SQLite DB for history. Press buttons → it sends `SIGSTOP`/`SIGCONT`/`SIGTERM` to the PID you typed.
9. A heartbeat message every 30 seconds proves the probe is alive (a dead probe with a live subscriber looks identical to a quiet system — heartbeats disambiguate).

**The 15-second spoken version of this flow:** "The probe reads process vitals from procfs twice a second, diffs against the previous sample to get CPU%, feeds a sliding-window similarity detector, and publishes everything over ZeroMQ. The auditor subscribes, enriches, and writes to SQLite. The controller subscribes for the live view and reads SQLite for history. Humans intervene through the controller with standard POSIX signals."

---

# PART 4: DEEP DIVES (every feature, in depth)

## 4.1 The Probe — `probe/`

### 4.1.1 ProcessMonitor (`process_monitor.cpp/h`)

**What it does**: Collects a `ProcessInfo` snapshot for a PID:

```cpp
struct ProcessInfo {
    pid_t pid;
    std::string command;      // from /proc/<pid>/cmdline
    double cpu_usage;         // percentage, 0–100
    long memory_usage;        // KB (RSS)
    long disk_read, disk_write;// KB (cumulative)
    long net_rx, net_tx;       // KB (placeholder — 0 for now)
    long long last_cpu_time;  // total ticks at last sample (cache key)
    std::chrono::time_point<...> last_check; // wall-clock of last sample
};
```

**How CPU% is computed** — the correct formula (after my fix):

```
CPU% = (Δticks × 100000) / (clock_ticks_per_sec × Δmilliseconds)
```

Derivation, which you should be able to do on a whiteboard:

- `/proc/<pid>/stat` fields 14–17 (utime, stime, cutime, cstime) are in **clock ticks**.
- `Δticks / clock_ticks_per_sec` = CPU-seconds consumed in the interval.
- `Δms / 1000` = wall-seconds elapsed.
- CPU% = (CPU-seconds / wall-seconds) × 100 = (Δticks × 1000 × 100) / (ticks_per_sec × Δms) = (Δticks × 100000) / (ticks_per_sec × Δms).

`clock_ticks_per_sec` comes from `sysconf(_SC_CLK_TCK)` (typically 100 on x86 Linux, **but 250 or 1000 on some ARM/embedded kernels** — which is exactly why the formula must divide by it, not multiply; see bug #6 in Part 5).

**The cache (`process_cache_`)**: An `unordered_map<pid_t, ProcessInfo>`. After each successful sample, we store the current sample (crucially including `last_cpu_time` and `last_check`) so the *next* call can diff. **First** sample for any PID returns CPU 0% — correct behavior, because a rate needs two points.

**Memory**: `/proc/<pid>/statm` has 7 fields; field 1 is total program size (virtual), **field 2 is resident (RSS)**. Multiply by page size (`sysconf(_SC_PAGESIZE)`, usually 4KB) to get bytes, divide by 1024 for KB.

**Disk I/O**: `/proc/<pid>/io`, lines `rchar:` and `wchar:` — cumulative bytes read/written through the syscall layer (not necessarily physical disk, but the right proxy for "is this process doing repetitive I/O"). Divide by 1024 for KB.

**Network**: Intentionally zero. Per-process network stats are genuinely hard on Linux (need eBPF or `/proc/net` correlation); we scoped it out. Being upfront about that is better than faking it.

**Child process discovery**: `getChildProcesses()` scans `/proc`, parses each numeric directory's `stat` field 4 (ppid), and returns children of a given parent — the foundation for monitoring a whole process tree (agent spawning subprocesses).

### 4.1.2 LoopDetector (`loop_detector.cpp/h`) — the heart of the system

**The intuition**: A process stuck in a tight loop has a *flat, repetitive* resource fingerprint — same CPU, same memory, same I/O pattern, sample after sample. A healthy process's metrics wander. So: keep a window of recent samples, and if a new sample is "similar" to many previous ones, suspect a loop.

**The data**: Each sample is a `ProcessFeatures` vector: `{cpu_usage, memory_mb, disk_read_kb, disk_write_kb, timestamp}`. The window is a **circular buffer** of 15 samples (default constructor in `main.cpp` uses `LoopDetector(15, 0.8, 3)`).

**Step 1 — Normalization (adaptive, after my fix)**: Raw features live on wildly different scales (CPU is 0–100, memory can be 0–several-GB). To compare them in one Euclidean space, each is squashed to 0–1. The original code divided by fixed maximums (100% CPU / 8GB memory / 100MB I/O) — and this caused the false-positive plague (Part 5, bug #4). Now:

- The detector tracks **observed min and max** for each feature across samples.
- After 10 warm-up samples, normalization uses the *observed range* for **this process**: `(value − observed_min) / (observed_max − observed_min)`.
- Below 10 samples (or when a feature's range is degenerate), fall back to fixed maximums.

**Why this matters in one sentence**: A tiny Python script that uses 30MB of RAM and 0.1% CPU would previously look identical, sample after sample, because dividing by 8GB flattened its memory differences to ~0.004 in normalized space — "similar" by construction. Now that its own range is 29.9–30.1MB, a 0.2MB wobble is *visible*.

**Step 2 — Similarity**: Euclidean distance over the four normalized features, converted to a 0–1 similarity via exponential decay:

```
distance   = √( (cpu₁−cpu₂)² + (mem₁−mem₂)² + (dr₁−dr₂)² + (dw₁−dw₂)² )   [normalized space]
similarity = exp(−distance / scale)          [scale = 10.0]
```

Exponential decay is a smooth, cheap kernel: distance 0 → similarity 1.0; large distance → similarity decays fast but never exactly 0. `scale=10` means samples need to be *quite* close to pass the 0.8 threshold (similarity 0.8 ↔ distance ≈ 2.2 in normalized space).

**Step 3 — Decision**: For the incoming sample, count how many stored window entries have similarity ≥ threshold (0.8). If `matches ≥ max(min_matches_for_alert, window_size/3)` → loop detected. My fix raised the effective bar to `window/3` (= 5 of 15) so one noisy spike can't fire it. Confidence = average similarity across the matched entries (so a *tight* loop reads 0.95+; a sloppy one reads 0.82).

**On detection**: The probe logs it, publishes it (message type `"1"`), and calls `reset()` — clearing the window and the adaptive stats — so each alert represents a *fresh* accumulation of evidence rather than spamming every 500ms forever.

**The circular buffer index bug**: The buffer position was a *function-local static* `static size_t pos = 0` — meaning **all instances shared one position**. Fine with one detector, silently corrupt with two. Fixed by making it a member `pos_` (and fixing `setWindowSize()` and `reset()` to reset it consistently).

### 4.1.3 SystemInterceptor (`system_interceptor.cpp/h`) — optional ptrace layer

**What it does**: Attaches to the target with `PTRACE_ATTACH`, then repeatedly `PTRACE_SYSCALL`s — the process stops at every syscall entry/exit, and we read registers (`PTRACE_GETREGS`) to record which syscall ran (x86-64: number in `orig_rax`, args in rdi, rsi, rdx, r10, r8, r9). It maintains per-syscall counters and a ring of 100 recent events, plus a callback registry (`setSyscallCallback`) so a future feature can react to a specific syscall.

**Why it exists**: Metrics tell you a process *is* looping; syscall traces hint at *what* it's doing (e.g., `read`/`write`/`openat` churn = file-polling loop; `nanosleep` storm = busy-wait). It's the next layer of resolution.

**The critical Linux rule** (this is your best systems-interview story): **all ptrace calls on a tracee must be issued from the same tracer thread.** The original code called `PTRACE_ATTACH` on the main thread but ran the `PTRACE_SYSCALL` polling loop on a spawned thread. Linux tracks the tracer as a thread, not a process — so the worker's ptrace calls hit `ESRCH` ("no such process") within ~a second even though the target was alive. The fix: move `PTRACE_ATTACH`, `waitpid`, the entire polling loop, *and* the final `PTRACE_DETACH` into the one interceptor thread. Now the same thread owns the entire tracee lifecycle.

**Graceful degradation**: If attach fails (permissions — e.g., inside unprivileged containers/WSL: "Operation not permitted"), the probe logs a warning and continues in **monitor-only mode**. Interception is an enhancement, not a dependency.

### 4.1.4 ZmqCommunicator (`zmq_communicator.cpp/h`)

- One PUB socket bound to `tcp://*:5555`.
- **Socket options**: `linger=0` (never block shutdown on unsent messages), `sndhwm=1000` (at most 1000 messages queued per subscriber; beyond that, drop — correct for telemetry).
- **Non-blocking sends** (`send_flags::dontwait`): if the buffer is full, we log and move on; the monitor must never stall because a dashboard stopped reading.
- Hand-rolled JSON serializer with **proper string escaping** (`escapeJsonString` handles quotes, backslashes, control chars as `\uXXXX`) — no external JSON library needed.
- **Simulation fallback**: compiled without `HAVE_ZMQ` (the CMake script pkg-configs for libzmq; if absent, it builds anyway), publishes become prints, and everything else still works. Degraded, never dead.
- The probe publishes **every sample** as type `"0"`, detections as type `"1"`, plus heartbeats (type `"3"`) every 30s.

### 4.1.5 main.cpp wiring

Signal handlers (SIGINT/SIGTERM → clean shutdown via an `atomic<bool>`), component construction with the demo defaults (`LoopDetector(15, 0.8, 3)`), the 500ms sampling loop, heartbeat timer, and a status line every 10 samples. Note the interceptor failure path — warning, not exit.

## 4.2 The Auditor — `auditor/`

One executable, three input modes (`argparse`-selected):

| Mode | Flag | Input | Use case |
|---|---|---|---|
| **ZMQ stream** | `--zmq` | Live pub/sub from the probe | Production / integration |
| **Log tail** | `--log-file <f>` | Follows a file like `tail -f` | Agent writes `[exec] <cmd>` lines to a log; auditor detects repeated command sequences |
| **Stdin JSON** | `--probe-input` | JSON lines piped in | Testing, gluing to other tools |

### Detection layers (this is a "defense in depth" story)

**Layer 1 — Syntactic loop detection** (log mode). Extract commands from `[exec] <command>` lines, keep the last `window_size` (default 5) as a state tuple, count repeated states in a map. The same 5-command window appearing `threshold` (default 3) times → `syntactic_loop` alert, then the counter resets (built-in dedup, so one persistent loop yields periodic — not constant — alerts).

**Layer 2 — Semantic analysis**. Even without an explicit loop, the auditor watches the *meaning* of recent lines:
- **All-errors window**: if every one of the last `window_size` lines matches the error regex (`error|fail|exception|not found|denied|invalid|timeout|connection refused|…`, compiled once) → `semantic_error_loop`.
- **Repeated error signature**: normalize each error line (replace digits with `#`, paths with `/PATH`) and if the *same signature* repeats ≥3 times → `repeated_error_pattern`. This is the "tried the same locked door 500 times" detector: details vary, shape doesn't.

**Layer 3 — Alert enrichment**. When the probe's ZMQ loop detection arrives, the auditor attaches semantic context, boosts confidence, and — the part I added — **writes it to the audit DB**.

### The persistence layer (the write path I added)

The `AuditViewer` class (in `controller/src/audit/viewer.py`) owns the SQLite schema — four indexed tables (`process_metrics`, `alerts`, `loop_detections`, `system_events`) — and previously had *only read* methods: a full viewer over a database nothing ever wrote to. I added the missing half:

```python
insert_process_metrics(timestamp, pid, command, cpu_usage, memory_usage,
                        disk_read, disk_write, net_sent, net_recv, status)
insert_alert(timestamp, alert_type, confidence, pid, details)
insert_loop_detection(timestamp, pid, confidence, cpu_usage, memory_usage, similar_samples)
insert_system_event(timestamp, event_type, source, description, severity)
```

Each is a parameterized `INSERT` with commit/close, wrapped in try/except with logging. The ZMQ listener thread dispatches by message type to the right insert. **Verified in integration**: 29 metric rows + 5 alerts + 5 loop detections captured during a 15-second probe run.

### Threading model

The ZMQ listener runs in a **daemon thread** (`threading.Thread(daemon=True)`) doing a non-blocking `recv_string(zmq.NOBLOCK)` loop with a 10ms sleep on `zmq.Again` (nothing waiting) — so Ctrl+C always kills the process (daemon threads don't block exit) and the listener never blocks the main thread.

## 4.3 The Controller — `controller/`

Two faces:

### 4.3.1 The Textual TUI (`controller/src/controller.py`)

A five-tab terminal dashboard:

1. **Monitoring** — live process table (PID, command, CPU%, memory, status) fed by ZMQ, plus an alerts table and control buttons.
2. **Snapshots** — create/restore/delete snapshots, listed with size and timestamp.
3. **Policies** — view policy sets; add/edit/delete flows.
4. **Audit Trail** — joins `alerts` and `loop_detections` from SQLite into one time-sorted table; filter; export **JSON** or **CSV**; acknowledge alerts (an `UPDATE alerts SET acknowledged=1` — the audit record is honest about what a human has seen).
5. **Settings** — sample interval, history size, automation toggle.

**The control primitives are dead simple — and that's the point**: Pause = `os.kill(pid, SIGSTOP)`. Resume = `SIGCONT`. Terminate = `SIGTERM`. POSIX already solved "how do I stop a process"; the value is the *decision support* (dashboards, detections, audit) wrapped around those three syscalls.

**ZMQ consumption**: `zmq.asyncio` SUB socket, subscribe-all, dispatch by `type` field — `process_info` updates the table, `loop_detection` appends an alert (bounded to the last 50).

### 4.3.2 The CLI (`controller/aether.py`)

A `subparsers`-based CLI for scripted/automation use: `snapshot --label`, `list`, `rewind --steps N`, `throttle --cpu % --memory MB`, `hint "text"`, `status`. It snapshots a **workspace directory** (copy everything except excluded dirs into `snapshots/<label>/`), which is genuinely restorable — unlike process snapshots, file trees restore with `copytree`. `rewind` deletes current contents and copies the target snapshot back: a working time-travel mechanism for an agent's working files.

### 4.3.3 SnapshotManager (`controller/src/snapshots/manager.py`)

For *processes*, takes a forensic snapshot: via `psutil` it captures exe, cmdline, status, create_time, ppid, environment, cwd, memory maps (per-region RSS/shared/private), open files (fd, position, mode), and network connections — all into `data.json`, archived as `tar.gz`, indexed in `metadata.json` (id, pid, timestamp, size, archive path).

**The honest part (I cleaned this up)**: the original wrote a placeholder `core.dump` file pretending to contain memory. I removed it. "Restore" today means: extract the archive and print a precise restoration guide — restart command, cwd, environment, open files — while *stating clearly* that full memory/register restoration requires external tooling (gdb's `generate-core-file`, or CRIU for true checkpoint/restore). In an interview this is a strength: "I removed fake capability and documented the real boundary."

### 4.3.4 PolicyManager (`controller/src/policies/manager.py`)

JSON-file-backed policy sets with defaults auto-provisioned on first run:

- `loop_detection`: enabled, confidence_threshold 0.8, window 5, auto_pause **false**, auto_snapshot **true**, notification level.
- `resource_thresholds`: CPU 80/95, memory 80/95, disk 90/98 (warning/critical).
- `monitoring`: sample interval 1.0s, history 300, alert cooldown 10s, max 5 alerts/min.
- `automation`: **disabled by default** — a deliberate human-in-the-loop default.

`evaluate_loop_detection(confidence, pid)` and `evaluate_resource_usage(cpu, mem, disk)` return *action recommendations* (alert / snapshot / pause) — the Controller decides what to execute. That separation (policy recommends, UI acts) keeps the safety logic testable.

### 4.3.5 AuditViewer (`controller/src/audit/viewer.py`)

The SQLite query layer: parameterized SELECTs with time/type/pid/confidence filters across all four tables, `acknowledge_alert`, 24-hour `get_statistics` (counts, averages, distinct PIDs), and `export_data` to JSON/CSV with per-type counts. Auto-creates the schema if the DB is missing, with indexes on the timestamp columns (fast recent-first queries).

## 4.4 Build system, Docker, and tests

- **CMake** (`probe/CMakeLists.txt`): C++20, `-Wall -Wextra -Wpedantic`, `pkg-config` for libzmq with the `HAVE_ZMQ` define — build degrades to simulation mode if ZMQ is absent, rather than failing.
- **Docker**: multi-stage (Ubuntu builder for the C++ probe, slim Python stages for auditor/controller, merged into a final Ubuntu image with a non-root `aetheros` user and a `pgrep` healthcheck). **Honest status: written but not CI-verified.**
- **Testing**: integration script (`integration_test.sh`) launches auditor + probe, then asserts DB row counts; helper scripts verify imports and DB inserts. **Honest status: no formal pytest/gtest framework** — a known gap and a good "what I'd do next" answer.

---

# PART 5: THE BUGS I FOUND AND FIXED (your best stories)

Each of these is a complete story with **symptom → diagnosis → fix → verification**. Interviewers love this structure. Practice telling each in 60–90 seconds.

## Bug #1 — The build was broken: wrong ZeroMQ option name

- **Symptom**: `make` fails; compiler rejects `zmq::sockopt::send_high_water_mark`.
- **Diagnosis**: cppzmq maps the raw libzmq option `ZMQ_SNDHWM` to the C++ name `sndhwm`. There is no `send_high_water_mark` in the API — the name was invented/remembered wrong.
- **Fix**: `publisher_->set(zmq::sockopt::sndhwm, sndhwm);` — one line, verified by a clean build against standard cppzmq.
- **Lesson**: API names must be checked against the actual headers, not memory. This also gates *everything* — a project that doesn't build can't have any other fix verified.

## Bug #2 — Ptrace across threads: the false "process no longer exists"

- **Symptom**: After attaching to a genuinely running process, within ~1 second: `ESRCH — process no longer exists`, and monitoring dies.
- **Diagnosis**: Linux's ptrace binds the tracee to **the specific thread** that attached. The code attached on the **main thread** (`initialize()`), then polled with `PTRACE_SYSCALL` and later detached from a **spawned worker thread**. From the kernel's perspective, an unrelated thread was issuing ptrace calls on someone else's tracee → `ESRCH`.
- **Fix**: Move the entire tracee lifecycle into the one interceptor thread — `PTRACE_ATTACH`, the initial `waitpid`, the polling loop, and `PTRACE_DETACH` all execute in `interceptorThread()`. Main thread only sets up state and joins.
- **Verification**: Attach now holds for the full run against a live process; no false ESRCH.
- **Deep talking point**: ptrace predates threads (it models a *parent* tracing a *child*), so its bookkeeping is per-thread (`task_struct` in kernel terms). This is documented ptrace behavior, not an implementation quirk.

## Bug #3 — The cache that was never written: CPU forever 0.0%

- **Symptom**: `cpu_usage` reads exactly `0.0` forever, no matter how busy the process is.
- **Diagnosis**: `getProcessInfo()` did `process_cache_.find(pid)` to get the *previous* sample for the delta — but **never stored the new sample**. There was never a "previous" sample; the diff branch never ran.
- **Fix**: One line at the end of a successful sample: `process_cache_[pid] = info;`.
- **Verification**: A busy process now reports real CPU (spot-checked against a manual `/proc/pid/stat` calculation).
- **Lesson**: When a value that requires state is a constant, suspect the state. "Always zero" or "always the default" is the smell of a never-updated cache.

## Bug #4 — Loop detector false positives on ordinary processes

- **Symptom**: A process doing **genuinely randomized** CPU work with randomized sleeps — definitively *not* looping — triggers `LOOP DETECTED` at 0.88–0.94 confidence almost immediately.
- **Diagnosis**: Normalization divided every feature by **fixed maximums** — CPU/100, memory/8192MB, disk/102400KB. For a small process, memory and disk live near zero, so 3 of 4 normalized features are flat ~0.00x regardless of behavior. With 3 of 4 dimensions effectively frozen, even jittery CPU samples were "similar enough" (≥0.8) against the 3-match rule. The detector was measuring *its own normalization artifacts*, not the process.
- **Fix (two-part)**:
  1. **Adaptive per-process normalization** — track observed min/max per feature; after a 10-sample warm-up, normalize by `(value − min) / (max − min)` over the *process's own* observed range. Now a 0.2MB wobble in a 30MB process is visible instead of crushed to 0.004.
  2. **Higher match bar** — require `max(min_matches, window_size/3)` matches (5 of 15 by default), so detection demands broad agreement across the window, not a lucky few.
- **Honest residual**: a process whose metrics are *truly* flat (an idle `sleep`) still matches itself — the detector flags genuinely-frozen states. That is arguably by design ("no behavioral change for N samples"), but say it out loud as a known tuning trade-off; it shows you understand the detector's semantics, not just its code.

## Bug #5 — `static size_t pos`: hidden shared state across instances

- **Symptom**: None today — exactly why it's dangerous.
- **Diagnosis**: `addFeatureSample()` used a **function-local static** as the circular-buffer index. Statics have one copy *per program*, not per object. Two `LoopDetector` instances would share one index and corrupt each other's windows. The current design (one detector per probe) masks it.
- **Fix**: Member variable `pos_`; also fixed `setWindowSize()` (which had its *own* static) and `reset()` to reset it consistently. Also cleaned up the member-initializer order to silence a `-Wreorder` warning.
- **Lesson to quote**: "Statics are program-global, not object-global. Any static used as object state is a latent bug waiting for the second instance."

## Bug #6 — A formula that was right by coincidence

- **Symptom**: None on the dev box. **Wrong everywhere `USER_HZ ≠ 100`.**
- **Original formula**: `(Δticks × clock_ticks) / (Δms × 10)`. Plug in x86's `CLK_TCK=100` and it collapses to `Δticks×10/Δms` — which happens to be right *only because* 100 sits in the sweet spot. On ARM/embedded kernels with 250 or 1000 ticks/sec it's off by 2.5×–10×.
- **Fix**: Derive it properly: CPU% = (Δticks / ticks_per_sec) ÷ (Δms / 1000) × 100 = `(Δticks × 100000) / (ticks_per_sec × Δms)`. Now `sysconf(_SC_CLK_TCK)` enters as a *divisor*, as dimensional analysis demands.
- **Interview gold**: this is a portability bug — the worst kind, invisible on your machine, wrong on someone else's. The phrase to use: **"the units canceled by coincidence."**

## Bug #7 — Memory: reading the wrong procfs field

- **Symptom**: Memory reported ~12GB for a process whose real usage was ~430MB.
- **Diagnosis**: `/proc/<pid>/statm`'s **field 1 is total virtual size**; **field 2 is RSS**. The code read field 1. (Virtual includes mapped files, reserved arenas — wildly larger than resident memory.)
- **Fix**: Read two fields, use the second: `statm >> size_pages >> resident_pages`. Verified against `ps` RSS.
- **Lesson**: procfs formats are positional contracts; off-by-one field reads "work" and are quietly wrong.

## Bug #8 — The auditor heard everything and understood nothing

- **Symptom**: Integration test passes messages (visible on the wire), database stays at 0 rows.
- **Diagnosis (two defects in the JSON handling)**:
  1. The probe serialized type as a **string** (`"type":"0"`); the auditor compared with **integer** equality (`msg_type == 0`). `"0" == 0` is false; every message fell through.
  2. `json.loads` on the outer message had already parsed `payload` into a **dict**; the auditor called `json.loads(payload)` again → TypeError, swallowed by a broad except → silent drop.
- **Fix**: coerce the type (`int(msg_type_raw)` with try/except) and branch on `isinstance(payload, str)` before parsing. **Then I found the broad `except` that hid defect 2 and made failures log loudly instead.**
- **Verification**: the same 15-second run now yields 29 metrics + 5 alerts + 5 loop-detections in SQLite.
- **Lesson**: two bugs *composed* into silence. And: a broad except that doesn't log is a bug factory — fail loudly in the debug path.

## Hygiene fixes (mention briefly, don't dwell)

- Deleted 7 junk files (scratch `.txt`s, `main.cpp.zmq_backup`, `main.cpp.pre_zmq`, `CMakeLists.txt.bak2`, a duplicate `controller_orig.py`).
- Removed unused heavy deps from auditor `requirements.txt` (pandas, numpy, scikit-learn) — the code never imported them; every unused dependency is install friction and CVE surface for nothing.
- Removed the fake core-dump placeholder in SnapshotManager and documented the real restoration boundary (gdb/CRIU).

---

# PART 6: INTERVIEW Q&A BANK

## A. The project in general

**Q: What does this project do in one sentence?**
> "It's a safety net for autonomous AI agents: a C++ probe watches their OS-level resource behavior and detects infinite/repetitive loops, a Python auditor analyzes and persists everything to an audit database, and a Python controller gives humans a live dashboard to intervene."

**Q: What was the hardest part?**
> "The loop detector's false positives. The detection *idea* — similarity across a sliding window — was fine, but fixed normalization constants meant light workloads looked flat in 3 of 4 dimensions and everything tripped the threshold. Diagnosing that required realizing the detector was measuring its own normalization artifacts, not the process. The fix — adaptive per-process normalization based on observed ranges — is simple to state, but only fell out of understanding exactly which dimension was frozen."

**Q: What would you do differently?**
> "Three things: (1) formal tests — I'd add gtest for the probe and pytest for the auditor from day one instead of integration scripts; (2) I'd separate 'channel' from 'state' for metrics — publish CPU/IO deltas rather than cumulative counters; (3) I'd put the loop detector's similarity parameters behind a config with a tuning harness so adjusting sensitivity is data-driven instead of hand-waved."

**Q: Is this production-ready?**
> "The monitoring and audit pipeline is. The ptrace interception needs a privilege model (containers need SYS_PTRACE), the loop detector's thresholds need per-workload tuning, and the Docker path isn't CI-verified. As a demo-interview project, the honest framing is: the core pipeline works end-to-end and is verified; the edges are documented as edges."

## B. Systems / Linux questions

**Q: Why read from /proc instead of using a library like psutil?**
> "Two reasons: (1) the probe is C++ and /proc is two orders of magnitude lighter than pulling Python bindings or heavy deps into the binary — we parse text files with ifstream; (2) /proc is the *source* psutil itself reads on Linux. Reading the primary source directly removes a dependency and gives exact control over parsing. The trade-off is fragility to format assumptions — which bit us once (the statm field bug), and the fix was reading the format spec."

**Q: Walk me through computing CPU usage for a process.**
> "Read `/proc/<pid>/stat`, fields 14–17: utime, stime, cutime, cstime, all in clock ticks. Sum them for total CPU time. Sample twice; the usage is the *delta*: CPU% = (Δticks ÷ ticks_per_sec) ÷ (Δwallclock_seconds) × 100. Two subtleties: you need `sysconf(_SC_CLK_TCK)` because tick rate isn't guaranteed to be 100 — and dividing by it rather than multiplying is exactly what a bug in this project got wrong; and the first sample for a PID can't produce a rate, so you cache the sample and return 0% until the second one."

**Q: What does ptrace do and where did it bite you?**
> "ptrace lets one process control another at the syscall boundary — attach, stop, single-step, read registers. We use PTRACE_SYSCALL to stop at every syscall entry/exit and record syscall numbers and args. The bite: Linux binds a tracee to the attaching *thread*. Our code attached on the main thread and polled from a worker, so the kernel rejected the worker's ptrace calls with ESRCH — a running process looked dead. Fix: one thread owns the whole tracee lifecycle — attach, wait, poll, detach."

**Q: RSS vs VSZ?**
> "VSZ is total virtual address space — everything mapped, including reserved-but-never-touched memory. RSS is resident set — pages actually in physical RAM. They differ by gigabytes for processes that map big files or reserve arenas. Our memory bug was reading statm field 1 (VSZ) instead of field 2 (RSS) — a 12GB reading on a 430MB process. For loop detection we care about RSS because behavioral change shows up in what's actually being touched."

**Q: Why does the probe use a 500ms sampling interval?**
> "Fast enough to catch loops within a couple of windows (the detector needs ~15 samples ≈ 7.5s of evidence), slow enough that monitoring costs well under 1% of a core. It's a deliberate resolution/overhead trade — and it's configurable in the policy layer."

## C. Architecture & design questions

**Q: Why pub/sub instead of request/response?**
> "The dominant data flow is telemetry — fire-and-forget, one-to-many. The probe shouldn't know or care whether zero or five consumers exist. Pub/sub matches that shape: no consumer? messages drop harmlessly. Slow consumer? ZeroMQ drops past the high-water mark rather than backing up the probe. Request/response would force the probe to manage consumer health, which inverts the dependency — the monitor would depend on the dashboards."

**Q: What happens if the auditor crashes?**
> "Probe keeps sampling and publishing; with no subscriber, ZeroMQ discards messages once the queue hits its high-water mark — no backlog, no probe impact. When the auditor comes back, it re-subscribes and gets fresh data. The gap exists only in the audit DB — which is the correct place to be intolerant of gaps, and is why heartbeats exist: a subscriber can distinguish 'probe died' from 'nothing to report.'"

**Q: Why SQLite and not Postgres?**
> "The write pattern is low-rate inserts (2/sec/probe) with read-mostly querying by a single UI — SQLite's exact sweet spot. Postgres buys concurrent writers and network access, neither of which this deployment needs, at the cost of a database server to operate. The schema is portable, so graduating to Postgres is a connection-string change plus an ORM shim, not a rewrite."

**Q: How would you scale to monitoring 1000 machines?**
> "The probe is already a standalone publisher, so the fan-in is the only change: multiple probes → one auditor. ZMQ scales fine over TCP but the auditor's SQLite write path becomes the bottleneck, so (1) batch inserts or move to a queue in front of the DB, (2) shard auditors by machine group, (3) add a message broker only if we need durability/replay — at which point I'd graduate from ZeroMQ to Kafka, keeping the same message schema."

**Q: Why is the Controller reading from both ZMQ *and* the database?**
> "Different data with different properties. ZMQ gives *live* events (append to the alerts table, update the process table) but pub/sub has no history — a message you didn't receive is gone. The DB is the durable record for anything historical (audit browsing, exports, statistics). So: ZMQ for 'now', SQLite for 'before now' — and the heartbeat tells you whether a silent 'now' means quiet or dead."

## D. Detection algorithm questions

**Q: Explain your loop-detection algorithm from scratch.**
> "Every 500ms the probe builds a 4-dimensional feature vector: CPU%, memory in MB, disk read KB, disk write KB. It keeps the last 15 in a circular window. Each new sample is normalized — dividing by fixed caps initially, then, after a 10-sample warm-up, by the min/max range the process itself has exhibited — so all dimensions are 0–1 and comparable. For each stored sample, compute Euclidean distance to the new one, convert to similarity with exponential decay, `exp(-distance/10)`. Count stored samples with similarity ≥ 0.8; if that count reaches max(3, window/3) = 5, declare a loop with confidence = the average similarity of the matches, publish it, and reset the window so the next alert re-accumulates evidence."

**Q: Why exponential decay for similarity?**
> "It's a smooth, monotonic kernel from distance to similarity: identical → 1.0, diverging → decays fast but never exactly zero, so a distant sample can still contribute weak evidence rather than a hard cutoff. It's also one exp() call — negligible cost at this window size. Alternatives: a hard threshold on distance (no gradient, worse confidence scoring) or cosine similarity (measures direction, wrong for magnitudes — we care that values repeat, not that they point the same way)."

**Q: What are the failure modes of this detector?**
> "Three, in honesty: (1) a truly flat process — an idle sleep — matches itself and fires; arguably correct ('no behavioral change'), but if it's noise for your workload, you add an activity gate (ignore detection when CPU < X%). (2) A loop with *wandering* metrics — e.g., a loop that allocates each iteration — evades similarity; that's why the auditor's error-signature layer exists as a second, orthogonal check. (3) Warm-up: the first 10 samples use fixed normalization, so a process that's repetitive from second zero may take a few seconds to fire."

**Q: How did you validate the detector?**
> "Two adversarial cases: a genuinely randomized workload (random CPU bursts + random sleeps) that previously fired at 0.88–0.94 confidence should NOT fire after the adaptive fix; and a deliberately frozen process should still fire. I also cross-checked reported CPU% against a manual /proc stat calculation. The honest caveat: no labeled dataset and no precision/recall numbers — that's a stated next step, not a claim."

## E. Language / implementation questions

**Q: Why C++20 specifically?**
> "Three features earn their keep: `std::chrono` for the wall-clock deltas (clean unit-safe arithmetic), `std::thread`/`std::atomic` for the interceptor and the shutdown flag, and modern initializers keeping the LoopDetector constructor honest — a `-Wreorder` warning actually caught an initializer-order mistake during the fix."

**Q: How does the probe shut down cleanly?**
> "Signal handlers set an `atomic<bool>` the sampling loop checks — SIGINT/SIGTERM both map to 'stop sampling'. On exit: join the interceptor thread (its loop checks the same flag), detach from any tracee, close the ZMQ socket with linger=0 so exit never blocks on unsent messages. Note the ptrace detach lives *inside* the interceptor thread — moving it out would recreate the cross-thread bug we fixed."

**Q: How is the auditor threaded?**
> "Main thread does argparse and mode dispatch; the ZMQ listener is a daemon thread doing non-blocking recv with a 10ms sleep on EAGAIN. Daemon means Ctrl+C kills the process without needing to join. SQLite connections are opened per-insert and closed immediately — fine at this rate, avoids sharing a connection across threads, which sqlite3 in Python doesn't love."

**Q: What's in the database schema?**
> "Four tables: `process_metrics` (timestamp, pid, command, cpu, memory, disk r/w, net, status), `alerts` (timestamp, type, confidence, pid, details, acknowledged flag), `loop_detections` (timestamp, pid, confidence, cpu, memory, sample count), `system_events` (timestamp, type, source, description, severity). Timestamp indexes on the three hot tables — everything the UI does is recent-first, so the index matches the access pattern."

## F. Behavioral / meta questions

**Q: Tell me about a time you debugged something hard.**
> Use Bug #2 (ptrace ESRCH). Structure: symptom (running process reported dead in ~1s) → hypothesis list (is the process actually dying? permissions? ptrace misuse?) → the tell (target was verifiably alive; the *error* was the lie) → the principle (ptrace binds to a thread, not a process) → the fix (single-thread ownership) → the generalization ("when the OS says something impossible, your model of the API is wrong, not the OS").

**Q: Tell me about a time you found a bug that wasn't yours / in code you inherited.**
> Use Bug #6 (CPU formula) — "the code was right on every machine it had ever run on, and wrong on entire CPU architectures. Portability bugs are the most insidious because testing can't reveal them; only dimensional analysis can. The moment I wrote the units down and watched clock_ticks land in the numerator where a divisor belonged, it was fixed in one line."

**Q: How do you feel about removing features?**
> "Did it twice: dropped the unused ML dependencies because the codebase never imported them — dead weight that lied about what the system was; and removed the fake core-dump file because a placeholder that implies capability is worse than an honest 'requires gdb/CRIU' note. Software that claims less and does it is more maintainable than software that claims more."

**Q: What's next for this project?**
> Prioritized: (1) formal test suite — pytest + gtest, CI on push; (2) per-workload tuning harness for the detector, producing real precision/recall numbers; (3) CRIU-based true snapshot restore to replace the informational restore; (4) an eBPF-based network metric layer to fill the one zero in ProcessInfo; (5) Kafka graduation path for multi-machine durability."

---

# PART 7: HONEST LIMITATIONS (know these before they find them)

If you claim a project is flawless, one question can sink you. These are the real limitations — own them before the interviewer does.

| # | Limitation | The honest line to say | Mitigation if asked |
|---|---|---|---|
| 1 | **Truly idle processes still "loop-detect"** | "A process with genuinely frozen metrics matches itself — the detector fires on 'no behavioral change,' which is arguably its definition of a loop but can be noise for idle daemons." | Add an activity gate: suppress detection when CPU and I/O deltas are both zero for the window. |
| 2 | **No labeled-dataset validation of the detector** | "I validated with adversarial spot tests — randomized non-loops and frozen loops — not with a labeled corpus producing precision/recall. That's the next step, not a claim I make." | Build the tuning harness; report precision/recall per workload. |
| 3 | **Snapshot restore is informational** | "File/workspace snapshots restore fully; *process* snapshots capture a complete forensic record, but memory/register restoration requires CRIU or gdb — and I removed the placeholder that implied otherwise." | CRIU integration is the roadmap item. |
| 4 | **Docker path unverified** | "The Dockerfile is a reasonable multi-stage build, but it isn't CI-verified — I flag that rather than claim it works." | Add a GitHub Actions job that builds the image. |
| 5 | **No formal unit-test framework** | "Testing is integration-script-based: end-to-end runs asserting DB row counts. Real unit tests are the top roadmap item." | gtest for LoopDetector math (pure functions — ideal unit-test targets), pytest for auditor. |
| 6 | **Network metrics are hardcoded zero** | "Per-process network accounting needs eBPF or netlink correlation; I scoped it out rather than shipping a fake number." | eBPF layer is the roadmap item. |
| 7 | **Single probe design** | "One probe watches one PID per process. The components are already decoupled so many-probe fan-in works; I just haven't exercised it." | Multi-probe integration test. |
| 8 | **ptrace needs privileges** | "Inside unprivileged containers or WSL, attach returns EPERM — the probe degrades to monitor-only by design, but full interception requires SYS_PTRACE." | Document the capability requirement; that's what the graceful-degradation path is for. |
| 9 | **Audit DB has a single writer** | "SQLite with per-insert connections — correct for 1 auditor, a bottleneck at 1000 machines." | Queue + batching, then Postgres. |
| 10 | **No auth on the ZMQ channel** | "ZMQ has none built in. Fine for localhost; cross-machine it needs SSH tunnels or CurveZMQ encryption." | CurveZMQ or tunneling. |

**The meta-line that ties this section together:**
> "Every one of these is a scoped decision with a known mitigation path — the difference between a project that's unfinished and one that's honest about its edges."

---

# PART 8: CHEAT SHEET (memorize cold)

## Names & versions
- **Project**: Aether-OS (Agentic-Ethical-Resource-Orchestration System)
- **Probe**: C++20, CMake, ZeroMQ PUB on `tcp://*:5555`
- **Auditor / Controller**: Python 3.8+; Controller uses **Textual** TUI; deps pyzmq + psutil
- **DB**: SQLite, 4 tables (`process_metrics`, `alerts`, `loop_detections`, `system_events`), timestamp-indexed

## Key numbers
| Parameter | Value |
|---|---|
| Sample interval | 500 ms |
| Loop window | 15 samples (≈ 7.5 s of evidence) |
| Similarity threshold | 0.8 |
| Matches to alert | max(3, window/3) = **5** |
| Adaptive warm-up | 10 samples |
| Similarity kernel | `exp(−distance / 10)` |
| Heartbeat | every 30 s |
| ZMQ sndhwm | 1000 messages, linger = 0 |
| Message size | ~200 bytes |
| Message types | 0=metrics, 1=loop, 2=event, 3=heartbeat, 4=error |

## Formulas
```
CPU%   = (Δticks × 100000) / (CLK_TCK × Δms)
RSS_KB = statm_field2 × PAGE_SIZE / 1024
similarity = exp(−EuclideanDistance(normalized features) / 10)
adaptive norm = (value − observed_min) / (observed_max − observed_min)
```

## procfs field map
```
/proc/<pid>/stat  fields 14–17 = utime, stime, cutime, cstime  (clock ticks)
/proc/<pid>/statm field 1 = VSZ (pages), field 2 = RSS (pages)
/proc/<pid>/io    rchar: / wchar:  (cumulative bytes)
/proc/<pid>/cmdline  NUL-separated argv
```

## Signals used
`SIGSTOP` = pause · `SIGCONT` = resume · `SIGTERM` = terminate · `SIGINT/SIGTERM` = probe shutdown

## The 8 bugs in 8 words each
1. sndhwm, not send_high_water_mark
2. ptrace: one thread owns the tracee
3. Cache written, finally
4. Normalize by observed range, not fixed max
5. static → member (`pos_`)
6. Divide by CLK_TCK, don't multiply
7. statm field 2 is RSS
8. `"0" != 0`; payload parsed twice

## The three-sentence architecture
> "Probe (C++) reads procfs every 500ms, diffs CPU against a cached sample, runs sliding-window similarity on {CPU, mem, disk} features, publishes JSON over ZMQ. Auditor (Python) subscribes, adds semantic checks, writes everything to SQLite. Controller (Textual TUI) subscribes for live view, reads SQLite for history, sends POSIX signals to intervene."

---

# PART 9: GLOSSARY (plain English, for any audience)

| Term | Plain-English meaning |
|---|---|
| **AI agent** | A program you give a goal to, and it works toward it on its own without you watching. |
| **PID** | Process ID — the OS's employee badge number for every running program. |
| **/proc filesystem** | A fake "folder" Linux maintains in memory where the OS publishes live stats about every process, refreshed continuously. |
| **CPU usage %** | What fraction of the last time period the process actually spent computing. |
| **Clock tick** | The OS's internal metronome beat for counting CPU time; `CLK_TCK` = beats per second. |
| **RSS / VSZ** | RSS = memory physically in use right now. VSZ = total memory *reserved* including untouched space. RSS is the truth. |
| **Infinite loop** | When a program repeats the same work forever with no exit — the computing equivalent of walking in circles. |
| **Sliding window** | A "last N items only" memory — like a whiteboard that keeps only the 15 most recent readings. |
| **Circular buffer** | A fixed-size array where new items overwrite the oldest — a whiteboard you erase-rewrite in order. |
| **Normalization** | Rescaling different units (%, MB, KB) onto a common 0–1 ruler so they can be compared fairly. |
| **Euclidean distance** | Straight-line distance between two points — the everyday notion of "how far apart." |
| **Exponential decay** | A curve that falls off fast and then levels out — used to turn "distance" into "similarity" between 0 and 1. |
| **ptrace** | A Linux debugging interface that lets one process say "stop after every OS call" to another — how debuggers work. |
| **Syscall** | Any request a program makes to the OS itself — open a file, start a network connection, sleep. |
| **ESRCH** | Kernel error code literally meaning "no such process" — but also returned when *you're* not allowed/knowledgeable to see it, which is how it lied to us. |
| **ZeroMQ (ZMQ)** | A tiny library for passing messages between programs — pre-built plumbing for the mailbox system. |
| **PUB/SUB** | Publisher/subscriber — a radio station model: the station broadcasts; anyone can tune in; the station doesn't know or care who's listening. |
| **High-water mark (sndhwm)** | The inbox size limit — past it, oldest messages get dropped instead of letting the queue grow forever. Correct behavior for live telemetry. |
| **Brokerless** | No middleman server between sender and receiver — one less thing to install, run, or crash. |
| **Heartbeat** | A periodic "still alive" ping — so silence is detectable as death rather than mistaken for calm. |
| **SQLite** | A database stored as one ordinary file — the Post-it note of databases; perfect for single-writer apps, zero setup. |
| **Audit trail** | The flight-data recorder: a permanent, timestamped record of what happened, for reconstruction and accountability. |
| **Textual (TUI)** | A Python framework for building rich dashboards that run *inside a terminal window* — no browser, no GUI toolkit. |
| **Snapshot** | A saved photograph of a program's state at one instant, used for forensic examination or rollback. |
| **CRIU** | Checkpoint/Restore In Userspace — a Linux tool that can genuinely freeze and resurrect a running process; the honest path to true snapshot-restore. |
| **SIGSTOP / SIGCONT / SIGTERM** | OS signals: "pause" / "unpause" / "please exit" — the three buttons on the dashboard. |
| **Graceful degradation** | The art of losing features without losing the system — probe without ZMQ prints locally; without ptrace it monitors only; never dies because an optional piece is missing. |
| **Cgroups** | Linux containers' resource knobs — where CPU/memory limits would be enforced for the throttling feature. |
| **eBPF** | A modern Linux facility for safely observing kernel activity — the future path for per-process network stats. |
| **Isolation Forest** | The ML anomaly-detection algorithm *listed in old docs* but *not implemented* — scrubbed from requirements. If asked: "it was aspirational in the docs; I removed the claim and kept the honest regex + repeated-state detector that actually runs." |

---

## Final advice

1. **Lead with the problem, not the tech.** "AI agents get stuck in loops" in 5 seconds beats 5 minutes of component inventory.
2. **Have the ptrace story polished.** It's your strongest "real systems engineering" evidence.
3. **Never claim the unimplemented.** The old README's ML claims are gone for a reason; if an interviewer finds stale docs, the answer is "that was aspiration, not implementation — I removed it."
4. **Numbers, numbers, numbers.** 500ms, 15-sample window, 0.8 threshold, 5 matches, 30s heartbeat, ~200-byte messages. Specificity reads as ownership.
5. **Every limitation with a mitigation.** That's the difference between junior and senior in one sentence.


