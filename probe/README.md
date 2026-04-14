# Probe Component

Real-time system monitoring agent written in C++20.

## Responsibilities
- Monitor AI agent processes (CPU, memory, disk, network)
- Detect reasoning loops using rolling hash of agent state
- Intercept system calls for safe intervention
- Communicate with Auditor via shared memory or message queue
- Trigger SIGSTOP/SIGCONT on target processes

## Key Features
- Low-overhead monitoring (<1% CPU impact)
- Rolling hash loop detection (Rabin-Karp or similar)
- eBPF integration option for kernel-level monitoring
- Process tree tracking to monitor agent children
- Configurable monitoring intervals

## Implementation Plan
1. Basic process monitoring (psutil-like in C++)
2. Rolling hash implementation for state fingerprinting
3. System call interception mechanism
4. Alerting interface to Auditor
5. Process control functions (SIGSTOP/SIGCONT)

## Dependencies
- C++20 compiler
- Linux headers (for syscalls, ptrace)
- Optional: eBPF dependencies (bpftool, libbpf)
- Optional: Boost.Asio for IPC