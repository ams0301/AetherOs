#ifndef SYSTEM_INTERCEPTOR_H
#define SYSTEM_INTERCEPTOR_H

#include <string>
#include <functional>
#include <unordered_map>
#include <vector>
#include <mutex>
#include <thread>
#include <atomic>
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <signal.h>
#include <unistd.h>
#include <sys/reg.h>
#include <sys/user.h>

namespace aetheros {
namespace probe {

class SystemInterceptor {
public:
    SystemInterceptor();
    ~SystemInterceptor();
    
    // Initialize the interceptor for a target process
    bool initialize(pid_t target_pid);
    
    // Clean up resources
    void cleanup();
    
    // Set callback for specific system calls
    void setSyscallCallback(int syscall_num, 
                           std::function<void(int, long*)> callback);
    
    // Remove callback for specific system calls
    void removeSyscallCallback(int syscall_num);
    
    // Enable/disable interception
    void setEnabled(bool enabled);
    
    // Check if interception is active
    bool isActive() const;
    
    // Get statistics about intercepted syscalls
    std::unordered_map<int, long> getSyscallCounts() const;
    
    // Get recent syscall events
    std::vector<std::pair<int, long>> getRecentEvents(size_t count = 10) const;
    
private:
    pid_t target_pid_;
    bool enabled_;
    bool active_;
    std::thread interceptor_thread_;
    std::atomic<bool> running_;
    
    // Syscall callbacks
    std::unordered_map<int, std::function<void(int, long*)>> syscall_callbacks_;
    
    // Statistics
    std::unordered_map<int, long> syscall_counts_;
    std::vector<std::pair<int, long>> recent_events_;
    mutable std::mutex stats_mutex_;
    
    // Thread function for ptrace interception
    void interceptorThread();
    
    // Helper to read syscall arguments from registers
    void getSyscallArguments(pid_t pid, long* args) const;
};

} // namespace probe
} // namespace aetheros

#endif // SYSTEM_INTERCEPTOR_H