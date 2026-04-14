#ifndef ZMQ_COMMUNICATOR_H
#define ZMQ_COMMUNICATOR_H

#include <string>
#include <functional>
#include <atomic>
#include <thread>
#include <chrono>
#include <mutex>
#include <condition_variable>

// Forward declare zmq types to avoid including zmq.hpp in header if not available
#ifdef HAVE_ZMQ
#include <zmq.hpp>
#endif

namespace aetheros {
namespace probe {

enum class MessageType {
    PROCESS_METRICS,
    LOOP_DETECTED,
    SYSTEM_EVENT,
    HEARTBEAT,
    ERROR
};

struct ZmqMessage {
    MessageType type;
    std::string payload;
    long long timestamp;
    int source_pid;
};

class ZmqCommunicator {
public:
    ZmqCommunicator(const std::string& endpoint = "tcp://*:5555");
    ~ZmqCommunicator();
    
    // Initialize the ZMQ publisher
    bool initialize();
    
    // Clean up resources
    void cleanup();
    
    // Publish a message
    bool publishMessage(const ZmqMessage& message);
    
    // Convenience methods for common message types
    bool publishProcessMetrics(double cpu_usage, long memory_kb, 
                              long disk_read_kb, long disk_write_kb);
    bool publishLoopDetection(double confidence, const std::string& details);
    bool publishSystemEvent(const std::string& event_type, const std::string& description);
    bool publishHeartbeat();
    bool publishError(const std::string& error_message);
    
    // Set publisher endpoint
    void setEndpoint(const std::string& endpoint);
    
    // Check if publisher is active
    bool isActive() const;
    
private:
#ifdef HAVE_ZMQ
    zmq::context_t* context_;
    zmq::socket_t* publisher_;
#endif
    
    std::string endpoint_;
    std::atomic<bool> initialized_;
    std::atomic<bool> active_;
    
    // Helper to serialize message to JSON-like string
    std::string serializeMessage(const ZmqMessage& message) const;
};

} // namespace probe
} // namespace aetheros

#endif // ZMQ_COMMUNICATOR_H