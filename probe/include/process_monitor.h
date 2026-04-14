#ifndef PROCESS_MONITOR_H
#define PROCESS_MONITOR_H

#include <string>
#include <vector>
#include <unordered_map>
#include <chrono>

namespace aetheros {
namespace probe {

struct ProcessInfo {
    pid_t pid;
    std::string command;
    double cpu_usage;      // percentage
    long memory_usage;     // KB
    long disk_read;        // KB
    long disk_write;       // KB
    long net_rx;           // KB
    long net_tx;           // KB
    long long last_cpu_time; // Last total CPU time in clock ticks
    std::chrono::time_point<std::chrono::steady_clock> last_check;
};

class ProcessMonitor {
public:
    ProcessMonitor();
    ~ProcessMonitor();
    
    // Monitor a specific process by PID
    bool monitorProcess(pid_t pid);
    
    // Get current process info (calculates CPU usage)
    ProcessInfo getProcessInfo(pid_t pid);
    
    // Get all child processes of a given PID
    std::vector<pid_t> getChildProcesses(pid_t parent_pid);
    
    // Update monitoring data (call periodically)
    void update();
    
private:
    // Helper to read CPU time from stat file
    long long getProcessCpuTime(pid_t pid);
    
    // Helper to parse /proc/[pid]/stat
    bool parseStatFile(pid_t pid, long long& utime, long long& stime, 
                      long long& cutime, long long& cstime,
                      long long& starttime);
    
    // Cache for process information
    std::unordered_map<pid_t, ProcessInfo> process_cache_;
    
    // Clock ticks per second (from sysconf)
    long clock_ticks_;
};

} // namespace probe
} // namespace aetheros

#endif // PROCESS_MONITOR_H