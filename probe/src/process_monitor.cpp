#include "process_monitor.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <unistd.h>
#include <sys/types.h>
#include <dirent.h>
#include <sys/stat.h>
#include <cstring>

namespace aetheros {
namespace probe {

ProcessMonitor::ProcessMonitor() {
    // Get clock ticks per second
    clock_ticks_ = sysconf(_SC_CLK_TCK);
    if (clock_ticks_ <= 0) {
        clock_ticks_ = 100; // Fallback
    }
}

ProcessMonitor::~ProcessMonitor() {
    // Destructor - cleanup resources
}

bool ProcessMonitor::monitorProcess(pid_t pid) {
    // Check if process exists
    std::string proc_path = "/proc/" + std::to_string(pid);
    struct stat buffer;
    return (stat(proc_path.c_str(), &buffer) == 0);
}

long long ProcessMonitor::getProcessCpuTime(pid_t pid) {
    std::string stat_path = "/proc/" + std::to_string(pid) + "/stat";
    std::ifstream stat_file(stat_path);
    if (!stat_file.is_open()) {
        return 0;
    }
    
    std::string line;
    std::getline(stat_file, line);
    std::istringstream iss(line);
    
    std::string field;
    // Skip first 13 fields (pid, comm, state, ppid, pgrp, session, tty_nr, tpgid, flags, minflt, cminflt, majflt, cmajflt)
    for (int i = 0; i < 13; i++) {
        if (!(iss >> field)) {
            stat_file.close();
            return 0;
        }
    }
    
    // utime (14th field) and stime (15th field)
    long long utime = 0, stime = 0;
    if (iss >> field) {
        utime = stoll(field);
    }
    if (iss >> field) {
        stime = stoll(field);
    }
    
    stat_file.close();
    return utime + stime;
}

bool ProcessMonitor::parseStatFile(pid_t pid, long long& utime, long long& stime, 
                                  long long& cutime, long long& cstime,
                                  long long& starttime) {
    std::string stat_path = "/proc/" + std::to_string(pid) + "/stat";
    std::ifstream stat_file(stat_path);
    if (!stat_file.is_open()) {
        return false;
    }
    
    std::string line;
    std::getline(stat_file, line);
    std::istringstream iss(line);
    
    std::string field;
    int field_num = 0;
    
    // Parse fields up to starttime (field 22)
    while (iss >> field && field_num <= 22) {
        switch(field_num) {
            case 13: utime = stoll(field); break;   // utime
            case 14: stime = stoll(field); break;   // stime
            case 15: cutime = stoll(field); break;  // cutime
            case 16: cstime = stoll(field); break;  // cstime
            case 21: starttime = stoll(field); break; // starttime
        }
        field_num++;
    }
    
    stat_file.close();
    return (field_num >= 22); // Successfully parsed at least up to starttime
}

ProcessInfo ProcessMonitor::getProcessInfo(pid_t pid) {
    ProcessInfo info = {pid, "", 0.0, 0, 0, 0, 0, 0, 0, std::chrono::steady_clock::now()};
    
    if (!monitorProcess(pid)) {
        return info;
    }
    
    // Read command line
    std::string cmdline_path = "/proc/" + std::to_string(pid) + "/cmdline";
    std::ifstream cmdline_file(cmdline_path);
    if (cmdline_file.is_open()) {
        std::getline(cmdline_file, info.command, '\0'); // null-terminated
        cmdline_file.close();
    }
    
    // Parse stat file for detailed information
    long long utime = 0, stime = 0, cutime = 0, cstime = 0, starttime = 0;
    if (parseStatFile(pid, utime, stime, cutime, cstime, starttime)) {
        // Calculate total process time
        long long total_time = utime + stime + cutime + cstime;
        
        // Get current time
        auto now = std::chrono::steady_clock::now();
        
        // Check if we have previous data for this process
        auto it = process_cache_.find(pid);
        if (it != process_cache_.end()) {
            const ProcessInfo& prev_info = it->second;
            
            // Calculate time difference
            auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(now - prev_info.last_check).count();
            if (duration > 0) {
                // Calculate CPU usage percentage
                long long time_diff = total_time - prev_info.last_cpu_time;
                double cpu_usage = (static_cast<double>(time_diff) / static_cast<double>(duration)) * 
                                  (static_cast<double>(clock_ticks_) / 10.0) * 100.0;
                info.cpu_usage = std::max(0.0, std::min(100.0, cpu_usage)); // Clamp to 0-100%
            }
            
            // Store current values for next calculation
            info.last_cpu_time = total_time;
        } else {
            // First time seeing this process, initialize
            info.last_cpu_time = total_time;
        }
        
        info.last_check = now;
    }
    
    // Read memory information from statm or status
    std::string statm_path = "/proc/" + std::to_string(pid) + "/statm";
    std::ifstream statm_file(statm_path);
    if (statm_file.is_open()) {
        long long resident;
        if (statm_file >> resident) {
            // resident is in pages, convert to KB
            long page_size = sysconf(_SC_PAGESIZE);
            info.memory_usage = (resident * page_size) / 1024;
        }
        statm_file.close();
    }
    
    // Read I/O statistics if available
    std::string io_path = "/proc/" + std::to_string(pid) + "/io";
    std::ifstream io_file(io_path);
    if (io_file.is_open()) {
        std::string line;
        while (std::getline(io_file, line)) {
            if (line.rfind("rchar:", 0) == 0) {
                // Read chars - approximate as bytes read
                std::istringstream iss(line.substr(6));
                long long bytes;
                if (iss >> bytes) {
                    info.disk_read = bytes / 1024; // Convert to KB
                }
            } else if (line.rfind("wchar:", 0) == 0) {
                // Written chars - approximate as bytes written
                std::istringstream iss(line.substr(6));
                long long bytes;
                if (iss >> bytes) {
                    info.disk_write = bytes / 1024; // Convert to KB
                }
            }
        }
        io_file.close();
    }
    
    // For network stats, we'd need to look at /proc/[pid]/net/dev or use other methods
    // For now, keeping as 0 (would require more complex implementation)
    info.net_rx = 0;
    info.net_tx = 0;
    
    return info;
}

std::vector<pid_t> ProcessMonitor::getChildProcesses(pid_t parent_pid) {
    std::vector<pid_t> children;
    DIR* dir = opendir("/proc");
    if (!dir) return children;
    
    struct dirent* entry;
    while ((entry = readdir(dir)) != nullptr) {
        // Check if entry is a numeric directory (PID)
        pid_t pid = 0;
        bool is_number = true;
        for (const char* c = entry->d_name; *c; ++c) {
            if (!isdigit(*c)) {
                is_number = false;
                break;
            }
            pid = pid * 10 + (*c - '0');
        }
        
        if (is_number && pid > 0) {
            // Get parent PID of this process
            std::string stat_path = std::string("/proc/") + entry->d_name + "/stat";
            std::ifstream stat_file(stat_path);
            if (stat_file.is_open()) {
                std::string line;
                std::getline(stat_file, line);
                std::istringstream iss(line);
                
                std::string field;
                // Skip pid (field 0)
                if (!(iss >> field)) {
                    stat_file.close();
                    continue;
                }
                // Get ppid (field 3)
                for (int i = 0; i < 3; i++) {
                    if (!(iss >> field)) {
                        break;
                    }
                }
                if (iss >> field) {
                    pid_t ppid = stol(field);
                    if (ppid == parent_pid) {
                        children.push_back(pid);
                    }
                }
                stat_file.close();
            }
        }
    }
    closedir(dir);
    return children;
}

void ProcessMonitor::update() {
    // In a real implementation, this would update internal caches
    #if 0
    // For now, just a placeholder
    #endif
}

} // namespace probe
} // namespace aetheros