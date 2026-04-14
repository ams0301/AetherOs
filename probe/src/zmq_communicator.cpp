#include "zmq_communicator.h"
#include <iostream>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <thread>

// Simple JSON-like serialization without external dependencies
std::string escapeJsonString(const std::string& str) {
    std::string result;
    result.reserve(str.size() * 2); // Reserve space for escaped characters
    
    for (char c : str) {
        switch (c) {
            case '\"': result += "\\\""; break;
            case '\\': result += "\\\\"; break;
            case '\b': result += "\\b"; break;
            case '\f': result += "\\f"; break;
            case '\n': result += "\\n"; break;
            case '\r': result += "\\r"; break;
            case '\t': result += "\\t"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    // Control character - encode as \uXXXX
                    char buf[8];
                    snprintf(buf, sizeof(buf), "\\u%04x", static_cast<int>(c) & 0xFFFF);
                    result += buf;
                } else {
                    result += c;
                }
        }
    }
    return result;
}

namespace aetheros {
namespace probe {

// Constructor
ZmqCommunicator::ZmqCommunicator(const std::string& endpoint)
    : endpoint_(endpoint), initialized_(false), active_(false) {
#ifdef HAVE_ZMQ
    context_ = nullptr;
    publisher_ = nullptr;
#endif
    // Constructor body is intentionally empty - all initialization in initializer list
}

// Destructor
ZmqCommunicator::~ZmqCommunicator() {
    cleanup();
}

bool ZmqCommunicator::initialize() {
#ifdef HAVE_ZMQ
    try {
        // Clean up any existing state
        cleanup();
        
        // Create ZMQ context and publisher socket
        context_ = new zmq::context_t(1);
        publisher_ = new zmq::socket_t(*context_, ZMQ_PUB);
        
        // Bind to endpoint
        publisher_->bind(endpoint_);
        
        // Set socket options for better reliability
        int linger = 0; // Don't block on close
        publisher_->set(zmq::sockopt::linger, linger);
        
        int sndhwm = 1000; // Set high water mark for send buffer
        publisher_->set(zmq::sockopt::send_high_water_mark, sndhwm);
        
        initialized_ = true;
        active_ = true;
        
        std::cout << "ZMQ Communicator initialized on " << endpoint_ << std::endl;
        return true;
    } catch (const zmq::error_t& e) {
        std::cerr << "ZMQ error during initialization: " << e.what() << std::endl;
        cleanup();
        return false;
    } catch (const std::exception& e) {
        std::cerr << "Error during ZMQ initialization: " << e.what() << std::endl;
        cleanup();
        return false;
    }
#else
    // ZMQ not available - log warning but continue in degraded mode
    std::cerr << "Warning: ZMQ not available, running in monitor-only mode" << std::endl;
    initialized_ = true; // Mark as initialized so other components don't fail
    active_ = false;
    return true;
#endif
}

void ZmqCommunicator::cleanup() {
#ifdef HAVE_ZMQ
    if (publisher_) {
        try {
            publisher_->close();
        } catch (...) {
            // Ignore errors during cleanup
        }
        delete publisher_;
        publisher_ = nullptr;
    }
    
    if (context_) {
        try {
            context_->close();
        } catch (...) {
            // Ignore errors during cleanup
        }
        delete context_;
        context_ = nullptr;
    }
#endif
    
    initialized_ = false;
    active_ = false;
}

bool ZmqCommunicator::publishMessage(const ZmqMessage& message) {
    if (!initialized_ || !active_) {
        return false;
    }
    
#ifdef HAVE_ZMQ
    try {
        std::string serialized = serializeMessage(message);
        zmq::message_t zmq_message(serialized.size());
        memcpy(zmq_message.data(), serialized.data(), serialized.size());
        
        // Non-blocking send
        auto result = publisher_->send(zmq_message, zmq::send_flags::dontwait);
        if (!result.has_value()) {
            // Handle send failure (could be due to high water mark)
            // In a production system, we might want to queue or drop oldest messages
            std::cerr << "Warning: Failed to send ZMQ message (buffer full?)" << std::endl;
            return false;
        }
        return true;
    } catch (const zmq::error_t& e) {
        if (errno != EAGAIN) { // EAGAIN is expected in non-blocking mode when buffer full
            std::cerr << "ZMQ send error: " << e.what() << std::endl;
        }
        return false;
    } catch (const std::exception& e) {
        std::cerr << "Error publishing ZMQ message: " << e.what() << std::endl;
        return false;
    }
#else
    // ZMQ not available - just log that we would have sent the message
    std::cout << "[ZMQ SIM] Would send: " << serializeMessage(message) << std::endl;
    return true;
#endif
}

bool ZmqCommunicator::publishProcessMetrics(double cpu_usage, long memory_kb, 
                                           long disk_read_kb, long disk_write_kb) {
    ZmqMessage msg;
    msg.type = MessageType::PROCESS_METRICS;
    msg.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    msg.source_pid = getpid(); // This would be the target PID in real usage
    
    // Create JSON payload
    std::stringstream ss;
    ss << std::fixed << std::setprecision(2);
    ss << "{"
       << "\"cpu_usage\":" << cpu_usage << ","
       << "\"memory_kb\":" << memory_kb << ","
       << "\"disk_read_kb\":" << disk_read_kb << ","
       << "\"disk_write_kb\":" << disk_write_kb
       << "}";
    
    msg.payload = ss.str();
    return publishMessage(msg);
}

bool ZmqCommunicator::publishLoopDetection(double confidence, const std::string& details) {
    ZmqMessage msg;
    msg.type = MessageType::LOOP_DETECTED;
    msg.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    msg.source_pid = getpid();
    
    std::stringstream ss;
    ss << std::fixed << std::setprecision(2);
    ss << "{"
       << "\"confidence\":" << confidence << ","
       << "\"details\":\"" << escapeJsonString(details) << "\""
       << "}";
    
    msg.payload = ss.str();
    return publishMessage(msg);
}

bool ZmqCommunicator::publishSystemEvent(const std::string& event_type, const std::string& description) {
    ZmqMessage msg;
    msg.type = MessageType::SYSTEM_EVENT;
    msg.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    msg.source_pid = getpid();
    
    std::stringstream ss;
    ss << "{"
       << "\"event_type\":\"" << escapeJsonString(event_type) << "\","
       << "\"description\":\"" << escapeJsonString(description) << "\""
       << "}";
    
    msg.payload = ss.str();
    return publishMessage(msg);
}

bool ZmqCommunicator::publishHeartbeat() {
    ZmqMessage msg;
    msg.type = MessageType::HEARTBEAT;
    msg.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    msg.source_pid = getpid();
    msg.payload = "{}"; // Empty payload for heartbeat
    
    return publishMessage(msg);
}

bool ZmqCommunicator::publishError(const std::string& error_message) {
    ZmqMessage msg;
    msg.type = MessageType::ERROR;
    msg.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    msg.source_pid = getpid();
    
    std::stringstream ss;
    ss << "{"
       << "\"error\":\"" << escapeJsonString(error_message) << "\""
       << "}";
    
    msg.payload = ss.str();
    return publishMessage(msg);
}

void ZmqCommunicator::setEndpoint(const std::string& endpoint) {
    // Only allow changing endpoint when not active
    if (!initialized_) {
        endpoint_ = endpoint;
    }
}

bool ZmqCommunicator::isActive() const {
    return initialized_ && active_;
}

std::string ZmqCommunicator::serializeMessage(const ZmqMessage& message) const {
    std::stringstream ss;
    ss << "{"
       << "\"type\":\"" << static_cast<int>(message.type) << "\","
       << "\"timestamp\":" << message.timestamp << ","
       << "\"source_pid\":" << message.source_pid << ","
       << "\"payload\":" << message.payload
       << "}";
    return ss.str();
}

} // namespace probe
} // namespace aetheros