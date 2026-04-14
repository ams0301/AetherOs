#include "process_monitor.h"
#include "loop_detector.h"
#include "system_interceptor.h"
#include "zmq_communicator.h"
#include <iostream>
#include <thread>
#include <chrono>
#include <csignal>
#include <atomic>
#include <sstream>
#include <iomanip>

std::atomic<bool> running(true);

void signalHandler(int signal) {
    if (signal == SIGINT || signal == SIGTERM) {
        running = false;
        std::cout << "\nShutting down probe..." << std::endl;
    }
}

int main(int argc, char* argv[]) {
    // Set up signal handler
    std::signal(SIGINT, signalHandler);
    std::signal(SIGTERM, signalHandler);
    
    std::cout << "Aether-OS Probe (Enhanced with ZMQ) starting..." << std::endl;
    
    // Initialize components
    aetheros::probe::ProcessMonitor process_monitor;
    aetheros::probe::LoopDetector loop_detector(15, 0.8, 3); // 15-sample window, 80% similarity, 3 matches for alert
    aetheros::probe::SystemInterceptor interceptor;
    aetheros::probe::ZmqCommunicator zmq_communicator("tcp://*:5555");
    
    // Target PID to monitor (default to self for demo, or take from args)
    pid_t target_pid = getpid();
    if (argc > 1) {
        target_pid = std::stoi(argv[1]);
    }
    
    std::cout << "Monitoring process: " << target_pid << std::endl;
    
    // Initialize ZMQ communicator
    bool zmq_initialized = zmq_communicator.initialize();
    if (zmq_initialized) {
        std::cout << "ZMQ Publisher initialized on tcp://*:5555" << std::endl;
    } else {
        std::cerr << "Warning: ZMQ initialization failed (continuing in local-only mode)" << std::endl;
    }
    
    // Initialize interceptor for target process
    bool interceptor_initialized = interceptor.initialize(target_pid);
    if (!interceptor_initialized) {
        std::cerr << "Warning: Failed to initialize system interceptor (continuing in monitor-only mode)" << std::endl;
        // Continue anyway - we can still monitor without interception
    }
    
    // Main monitoring loop
    size_t sample_count = 0;
    auto last_heartbeat = std::chrono::steady_clock::now();
    const auto heartbeat_interval = std::chrono::seconds(30); // Send heartbeat every 30 seconds
    
    while (running) {
        // Get process information
        aetheros::probe::ProcessInfo info = process_monitor.getProcessInfo(target_pid);
        
        // Create feature sample for loop detection
        aetheros::probe::ProcessFeatures features;
        features.cpu_usage = info.cpu_usage;
        features.memory_mb = static_cast<double>(info.memory_usage) / 1024.0; // Convert KB to MB
        features.disk_read_kb = static_cast<double>(info.disk_read);
        features.disk_write_kb = static_cast<double>(info.disk_write);
        features.timestamp = std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()
        ).count();
        
        // Add sample to loop detector
        loop_detector.addFeatureSample(features);
        
        // Publish process metrics via ZMQ (if available)
        if (zmq_communicator.isActive()) {
            zmq_communicator.publishProcessMetrics(
                info.cpu_usage, 
                info.memory_usage, 
                info.disk_read, 
                info.disk_write
            );
        }
        
        // Check for loops
        if (loop_detector.isLoopDetected()) {
            double confidence = loop_detector.getLoopConfidence();
            std::string details = loop_detector.getLoopDetails();
            
            std::cout << "[" << std::chrono::system_clock::to_time_t(std::chrono::system_clock::now()) 
                      << "] LOOP DETECTED! Confidence: " << std::fixed << std::setprecision(2) << confidence << std::endl;
            
            // Publish loop detection via ZMQ
            if (zmq_communicator.isActive()) {
                zmq_communicator.publishLoopDetection(confidence, details);
            }
            
            // In a real implementation, we would:
            // 1. Notify auditor via ZMQ
            // 2. Possibly pause the process for analysis
            // 3. Trigger detailed investigation
            
            // For demo, we'll reset after detection to allow continued monitoring
            loop_detector.reset();
        }
        
        // Send periodic heartbeat
        auto now = std::chrono::steady_clock::now();
        if (now - last_heartbeat >= heartbeat_interval) {
            if (zmq_communicator.isActive()) {
                zmq_communicator.publishHeartbeat();
            }
            last_heartbeat = now;
        }
        
        // Periodic status output (every 10 samples)
        sample_count++;
        if (sample_count % 10 == 0) {
            std::cout << "[" << std::chrono::system_clock::to_time_t(std::chrono::system_clock::now()) 
                      << "] PID: " << info.pid 
                      << " | CPU: " << std::fixed << std::setprecision(1) << info.cpu_usage << "%"
                      << " | MEM: " << info.memory_usage << "KB"
                      << " | Samples: " << sample_count;
            
            if (zmq_communicator.isActive()) {
                std::cout << " | ZMQ: ACTIVE";
            } else {
                std::cout << " | ZMQ: INACTIVE";
            }
            
            if (loop_detector.isLoopDetected()) {
                std::cout << " | *** LOOP DETECTED ***";
                std::cout << " | Confidence: " << std::fixed << std::setprecision(2) 
                          << loop_detector.getLoopConfidence();
            }
            std::cout << std::endl;
        }
        
        // Sleep briefly to avoid excessive CPU usage
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
    
    // Cleanup
    interceptor.cleanup();
    zmq_communicator.cleanup();
    std::cout << "Aether-OS Probe stopped." << std::endl;
    
    return 0;
}