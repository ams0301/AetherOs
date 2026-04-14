#include "system_interceptor.h"
#include <iostream>
#include <cstring>
#include <cerrno>
#include <chrono>
#include <thread>

namespace aetheros {
namespace probe {

SystemInterceptor::SystemInterceptor()
    : target_pid_(0), enabled_(false), active_(false), running_(false) {
    // Constructor
}

SystemInterceptor::~SystemInterceptor() {
    cleanup();
}

bool SystemInterceptor::initialize(pid_t target_pid) {
    // Clean up any existing state
    cleanup();
    
    target_pid_ = target_pid;
    
    // Check if process exists
    if (kill(target_pid_, 0) != 0) {
        std::cerr << "Error: Process " << target_pid_ << " does not exist" << std::endl;
        return false;
    }
    
    // Attach to the process using ptrace
    if (ptrace(PTRACE_ATTACH, target_pid_, nullptr, nullptr) == -1) {
        std::cerr << "Error: Failed to attach to process " << target_pid_ 
                  << ": " << strerror(errno) << std::endl;
        return false;
    }
    
    // Wait for the process to stop
    int status;
    if (waitpid(target_pid_, &status, 0) == -1) {
        std::cerr << "Error: Failed to wait for process " << target_pid_ << std::endl;
        ptrace(PTRACE_DETACH, target_pid_, nullptr, nullptr);
        return false;
    }
    
    // Check if process stopped due to our attach
    if (!WIFSTOPPED(status)) {
        std::cerr << "Error: Process " << target_pid_ << " did not stop as expected" << std::endl;
        ptrace(PTRACE_DETACH, target_pid_, nullptr, nullptr);
        return false;
    }
    
    // Start the interception thread
    running_ = true;
    enabled_ = true;
    active_ = true;
    interceptor_thread_ = std::thread(&SystemInterceptor::interceptorThread, this);
    
    std::cout << "SystemInterceptor initialized and attached to PID " << target_pid_ << std::endl;
    return true;
}

void SystemInterceptor::cleanup() {
    if (running_) {
        running_ = false;
        if (interceptor_thread_.joinable()) {
            interceptor_thread_.join();
        }
    }
    
    if (active_) {
        // Detach from the process
        if (ptrace(PTRACE_DETACH, target_pid_, nullptr, nullptr) == -1) {
            std::cerr << "Warning: Failed to detach from process " << target_pid_ 
                      << ": " << strerror(errno) << std::endl;
        } else {
            std::cout << "SystemInterceptor detached from PID " << target_pid_ << std::endl;
        }
        active_ = false;
    }
    
    enabled_ = false;
    target_pid_ = 0;
    
    // Clear statistics
    {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        syscall_counts_.clear();
        recent_events_.clear();
    }
}

void SystemInterceptor::setSyscallCallback(int syscall_num, 
                                         std::function<void(int, long*)> callback) {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    syscall_callbacks_[syscall_num] = callback;
}

void SystemInterceptor::removeSyscallCallback(int syscall_num) {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    syscall_callbacks_.erase(syscall_num);
}

void SystemInterceptor::setEnabled(bool enabled) {
    enabled_ = enabled;
    if (!enabled && active_) {
        // Note: We don't automatically detach here as it might break monitoring
        // The user should call cleanup() or disable via other means
    }
}

bool SystemInterceptor::isActive() const {
    return active_ && enabled_;
}

void SystemInterceptor::getSyscallArguments(pid_t pid, long* args) const {
    // Read the registers to get syscall arguments
    // On x86_64: syscall number in RAX, args in RDI, RSI, RDX, R10, R8, R9
    struct user_regs_struct regs;
    
    if (ptrace(PTRACE_GETREGS, pid, nullptr, &regs) == 0) {
        args[0] = regs.rdi;
        args[1] = regs.rsi;
        args[2] = regs.rdx;
        args[3] = regs.r10;
        args[4] = regs.r8;
        args[5] = regs.r9;
    } else {
        // Zero out arguments if we can't read registers
        std::memset(args, 0, sizeof(long) * 6);
    }
}

void SystemInterceptor::interceptorThread() {
    std::cout << "Interceptor thread started for PID " << target_pid_ << std::endl;
    
    while (running_) {
        try {
            // Continue the process to execute one instruction
            if (ptrace(PTRACE_SYSCALL, target_pid_, nullptr, nullptr) == -1) {
                if (errno == ESRCH) {
                    // Process no longer exists
                    std::cerr << "Process " << target_pid_ << " no longer exists" << std::endl;
                    break;
                }
                std::cerr << "Error in PTRACE_SYSCALL: " << strerror(errno) << std::endl;
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
                continue;
            }
            
            // Wait for the process to stop (either entering or exiting syscall)
            int status;
            if (waitpid(target_pid_, &status, 0) == -1) {
                if (errno == EINTR) {
                    continue; // Interrupted by signal, try again
                }
                std::cerr << "Error in waitpid: " << strerror(errno) << std::endl;
                break;
            }
            
            // Check if process stopped or exited
            if (WIFEXITED(status) || WIFSIGNALED(status)) {
                std::cout << "Process " << target_pid_ << " has exited" << std::endl;
                break;
            }
            
            // Process stopped due to ptrace - check if it's a syscall entry or exit
            struct user_regs_struct regs;
            if (ptrace(PTRACE_GETREGS, target_pid_, nullptr, &regs) == -1) {
                std::cerr << "Error getting registers: " << strerror(errno) << std::endl;
                continue;
            }
            
            // On x86_64, we can determine entry/exit by checking if ORIG_RAX is valid
            // Actually, PTRACE_SYSCALL stops on both entry and exit
            // We need to track state or check if we're entering/exiting
            
            // Simple approach: treat every stop as a syscall event
            // In reality, we'd want to distinguish entry vs exit
            long syscall_num = regs.orig_rax; // For x86_64
            
            // Only process if it's a valid syscall number
            if (syscall_num >= 0 && syscall_num < 512) { // Reasonable upper bound
                long args[6];
                getSyscallArguments(target_pid_, args);
                
                // Update statistics
                {
                    std::lock_guard<std::mutex> lock(stats_mutex_);
                    syscall_counts_[syscall_num]++;
                    
                    // Keep recent events (limit to 100 to prevent unbounded growth)
                    recent_events_.push_back(std::make_pair(syscall_num, args[0]));
                    if (recent_events_.size() > 100) {
                        recent_events_.erase(recent_events_.begin());
                    }
                }
                
                // Call registered callback if any
                std::function<void(int, long*)> callback;
                {
                    std::lock_guard<std::mutex> lock(stats_mutex_);
                    auto it = syscall_callbacks_.find(syscall_num);
                    if (it != syscall_callbacks_.end()) {
                        callback = it->second;
                    }
                }
                
                if (callback) {
                    try {
                        callback(syscall_num, args);
                    } catch (const std::exception& e) {
                        std::cerr << "Error in syscall callback: " << e.what() << std::endl;
                    } catch (...) {
                        std::cerr << "Unknown error in syscall callback" << std::endl;
                    }
                }
            }
            
        } catch (const std::exception& e) {
            std::cerr << "Exception in interceptor thread: " << e.what() << std::endl;
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        } catch (...) {
            std::cerr << "Unknown exception in interceptor thread" << std::endl;
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
    
    std::cout << "Interceptor thread ending for PID " << target_pid_ << std::endl;
}

std::unordered_map<int, long> SystemInterceptor::getSyscallCounts() const {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    return syscall_counts_;
}

std::vector<std::pair<int, long>> SystemInterceptor::getRecentEvents(size_t count) const {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    size_t actual_count = std::min(count, recent_events_.size());
    if (actual_count == 0) {
        return {};
    }
    return std::vector<std::pair<int, long>>(recent_events_.end() - actual_count, recent_events_.end());
}

} // namespace probe
} // namespace aetheros