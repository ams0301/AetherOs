#include "loop_detector.h"
#include <iostream>
#include <algorithm>
#include <cmath>
#include <sstream>
#include <iomanip>

namespace aetheros {
namespace probe {

LoopDetector::LoopDetector(size_t window_size, double similarity_threshold, 
                          size_t min_matches_for_alert)
    : window_size_(window_size), similarity_threshold_(similarity_threshold),
      min_matches_for_alert_(min_matches_for_alert),
      feature_window_(), match_flags_(), pos_(0),
      loop_detected_(false), confidence_(0.0), loop_details_(""),
      cpu_max_(100.0), memory_max_(8192.0), disk_io_max_(102400.0),
      cpu_min_observed_(100.0), cpu_max_observed_(0.0),
      mem_min_observed_(8192.0), mem_max_observed_(0.0),
      disk_min_observed_(102400.0), disk_max_observed_(0.0),
      samples_collected_(0) {
    // Initialize with empty window
    feature_window_.resize(window_size_);
    match_flags_.resize(window_size_, false);
    
    // Initialize with invalid timestamps to mark empty slots
    for (auto& features : feature_window_) {
        features.timestamp = -1;
    }
}

LoopDetector::~LoopDetector() {
    // Destructor
}

double LoopDetector::calculateSimilarity(const ProcessFeatures& f1, const ProcessFeatures& f2) const {
    // Handle invalid timestamps
    if (f1.timestamp < 0 || f2.timestamp < 0) {
        return 0.0;
    }
    
    // Calculate Euclidean distance in normalized space
    double cpu_diff = f1.cpu_usage - f2.cpu_usage;
    double mem_diff = f1.memory_mb - f2.memory_mb;
    double disk_read_diff = f1.disk_read_kb - f2.disk_read_kb;
    double disk_write_diff = f1.disk_write_kb - f2.disk_write_kb;
    
    double distance = std::sqrt(
        cpu_diff * cpu_diff +
        mem_diff * mem_diff +
        disk_read_diff * disk_read_diff +
        disk_write_diff * disk_write_diff
    );
    
    // Convert distance to similarity (0 = identical, larger = more different)
    // We'll use a simple exponential decay: similarity = exp(-distance / scale)
    // Scale factor determines how quickly similarity drops with distance
    double scale = 10.0; // Adjust based on expected variation
    double similarity = std::exp(-distance / scale);
    
    return similarity;
}

ProcessFeatures LoopDetector::normalizeFeatures(const ProcessFeatures& features) const {
    ProcessFeatures normalized = features;
    
    // Adaptive normalization: use observed min/max if we have enough samples
    // Otherwise fall back to fixed maximums
    double cpu_max = cpu_max_;
    double cpu_min = 0.0;
    double mem_max = memory_max_;
    double mem_min = 0.0;
    double disk_max = disk_io_max_;
    double disk_min = 0.0;
    
    if (samples_collected_ >= 10) {
        // Use observed ranges with some padding
        cpu_max = std::max(cpu_max_observed_, cpu_max_ * 0.1);
        cpu_min = cpu_min_observed_;
        mem_max = std::max(mem_max_observed_, memory_max_ * 0.01);
        mem_min = mem_min_observed_;
        disk_max = std::max(disk_max_observed_, disk_io_max_ * 0.01);
        disk_min = disk_min_observed_;
    }
    
    // Normalize to 0-1 range based on observed or expected ranges
    if (cpu_max > cpu_min) {
        normalized.cpu_usage = std::min(1.0, std::max(0.0, (features.cpu_usage - cpu_min) / (cpu_max - cpu_min)));
    } else {
        normalized.cpu_usage = 0.0;
    }
    
    if (mem_max > mem_min) {
        normalized.memory_mb = std::min(1.0, std::max(0.0, (features.memory_mb - mem_min) / (mem_max - mem_min)));
    } else {
        normalized.memory_mb = 0.0;
    }
    
    if (disk_max > disk_min) {
        normalized.disk_read_kb = std::min(1.0, std::max(0.0, (features.disk_read_kb - disk_min) / (disk_max - disk_min)));
        normalized.disk_write_kb = std::min(1.0, std::max(0.0, (features.disk_write_kb - disk_min) / (disk_max - disk_min)));
    } else {
        normalized.disk_read_kb = 0.0;
        normalized.disk_write_kb = 0.0;
    }
    
    return normalized;
}

void LoopDetector::addFeatureSample(const ProcessFeatures& features) {
    // Update observed min/max for adaptive normalization
    cpu_min_observed_ = std::min(cpu_min_observed_, features.cpu_usage);
    cpu_max_observed_ = std::max(cpu_max_observed_, features.cpu_usage);
    mem_min_observed_ = std::min(mem_min_observed_, features.memory_mb);
    mem_max_observed_ = std::max(mem_max_observed_, features.memory_mb);
    disk_min_observed_ = std::min(disk_min_observed_, std::min(features.disk_read_kb, features.disk_write_kb));
    disk_max_observed_ = std::max(disk_max_observed_, std::max(features.disk_read_kb, features.disk_write_kb));
    samples_collected_++;
    
    // Shift window: remove oldest, add newest
    
    // Store the sample
    feature_window_[pos_] = features;
    
    // Reset match flags for this position
    match_flags_[pos_] = false;
    
    // Check for similarity with previous samples in window
    size_t matches = 0;
    double total_similarity = 0.0;
    
    for (size_t i = 0; i < window_size_; i++) {
        // Skip self-comparison and empty slots
        if (i != pos_ && feature_window_[i].timestamp >= 0) {
            double similarity = calculateSimilarity(feature_window_[i], features);
            
            if (similarity >= similarity_threshold_) {
                matches++;
                total_similarity += similarity;
                match_flags_[i] = true;  // Mark that this sample matched something
            }
        }
    }
    
    // Mark current position if it matched any previous samples
    if (matches > 0) {
        match_flags_[pos_] = true;
    }
    
    // Determine if we have a loop
    // Require a higher threshold of matches to reduce false positives
    size_t required_matches = std::max(min_matches_for_alert_, window_size_ / 3);
    loop_detected_ = (matches >= required_matches);
    
    if (loop_detected_) {
        // Calculate average similarity for confidence
        confidence_ = total_similarity / matches;
        
        // Generate details string
        std::stringstream ss;
        ss << "Loop detected: " << matches << " similar samples in window "
           << "(threshold: " << similarity_threshold_ << ", confidence: "
           << std::fixed << std::setprecision(2) << confidence_ << ")";
        
        loop_details_ = ss.str();
    } else {
        confidence_ = 0.0;
        loop_details_ = "No loop detected";
    }
    
    // Move to next position (circular buffer)
    pos_ = (pos_ + 1) % window_size_;
}

bool LoopDetector::isLoopDetected() const {
    return loop_detected_;
}

double LoopDetector::getLoopConfidence() const {
    return confidence_;
}

std::string LoopDetector::getLoopDetails() const {
    return loop_details_;
}

void LoopDetector::reset() {
    // Clear the window
    for (auto& features : feature_window_) {
        features.timestamp = -1;
    }
    std::fill(match_flags_.begin(), match_flags_.end(), false);
    
    // Reset adaptive normalization state
    cpu_min_observed_ = 100.0;
    cpu_max_observed_ = 0.0;
    mem_min_observed_ = 8192.0;
    mem_max_observed_ = 0.0;
    disk_min_observed_ = 102400.0;
    disk_max_observed_ = 0.0;
    samples_collected_ = 0;
    pos_ = 0;
    
    loop_detected_ = false;
    confidence_ = 0.0;
    loop_details_ = "Detector reset";
}

void LoopDetector::setSimilarityThreshold(double threshold) {
    if (threshold >= 0.0 && threshold <= 1.0) {
        similarity_threshold_ = threshold;
    }
}

void LoopDetector::setWindowSize(size_t size) {
    if (size > 0) {
        window_size_ = size;
        feature_window_.resize(window_size_);
        match_flags_.resize(window_size_);
        
        // Reinitialize with invalid timestamps
        for (auto& features : feature_window_) {
            features.timestamp = -1;
        }
        
        // Reset position
        pos_ = 0;
    }
}

} // namespace probe
} // namespace aetheros