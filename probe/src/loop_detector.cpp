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
      loop_detected_(false), confidence_(0.0), loop_details_("") {
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
    
    // Distance is measured in per-dimension deadband units: each feature's
    // difference is divided by a noise floor representing the smallest
    // change in that resource that is behaviorally meaningful.
    // (Disk features are per-sample rates, not cumulative counters.)
    constexpr double kCpuDeadband = 5.0;     // percent
    constexpr double kMemDeadband = 4.0;     // MB
    constexpr double kDiskDeadband = 512.0;   // KB per sample (~1 MB/s)
    
    double cpu_d = (f1.cpu_usage - f2.cpu_usage) / kCpuDeadband;
    double mem_d = (f1.memory_mb - f2.memory_mb) / kMemDeadband;
    double disk_read_d = (f1.disk_read_kb - f2.disk_read_kb) / kDiskDeadband;
    double disk_write_d = (f1.disk_write_kb - f2.disk_write_kb) / kDiskDeadband;
    
    double distance = std::sqrt(
        cpu_d * cpu_d +
        mem_d * mem_d +
        disk_read_d * disk_read_d +
        disk_write_d * disk_write_d
    );
    
    // Similarity = exp(-distance), with distance in deadband units (scale 1).
    // Threshold 0.8 <=> distance <= ~0.22: all dimensions within ~22% of
    // one deadband. Identical samples score 1.0; a 6% CPU move alone scores
    // ~0.30. The threshold is reachable from both sides.
    double similarity = std::exp(-distance);
    
    return similarity;
}

void LoopDetector::addFeatureSample(const ProcessFeatures& features) {
    // A loop alert is only meaningful if the process is actually consuming
    // resources: an idle process matching itself is not a harmful loop.
    constexpr double kActivityCpuFloor = 5.0;  // avg CPU% over the window
    
    // Store the sample
    feature_window_[pos_] = features;
    
    // Reset match flags for this position
    match_flags_[pos_] = false;
    
    // Check for similarity with previous samples in window,
    // while accumulating window activity statistics
    size_t matches = 0;
    double total_similarity = 0.0;
    
    size_t valid_samples = 0;
    double cpu_sum = 0.0;
    double disk_total = features.disk_read_kb + features.disk_write_kb;
    double disk_max = disk_total;
    
    for (size_t i = 0; i < window_size_; i++) {
        if (feature_window_[i].timestamp < 0) {
            continue;  // Empty slot
        }
        
        valid_samples++;
        cpu_sum += feature_window_[i].cpu_usage;
        double sample_disk_total = feature_window_[i].disk_read_kb + feature_window_[i].disk_write_kb;
        disk_max = std::max(disk_max, sample_disk_total);
        
        if (i != pos_) {
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
    
    // Activity gate: window must show real resource consumption.
    // Disk features are rates, so any nonzero rate in the window counts.
    bool active = false;
    if (valid_samples > 0) {
        double avg_cpu = cpu_sum / static_cast<double>(valid_samples);
        active = (avg_cpu >= kActivityCpuFloor) || (disk_max > 0.0);
    }
    
    // Determine if we have a loop
    // Require a higher threshold of matches to reduce false positives
    size_t required_matches = std::max(min_matches_for_alert_, window_size_ / 3);
    
    // Consecutive-evidence confirmation: alert only when the current
    // sample AND the previous sample both carried sufficient matches.
    bool evidence = active && (matches >= required_matches);
    loop_detected_ = evidence && prev_evidence_;
    prev_evidence_ = evidence;
    
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
    // Clear the evidence window
    for (auto& features : feature_window_) {
        features.timestamp = -1;
    }
    std::fill(match_flags_.begin(), match_flags_.end(), false);
    pos_ = 0;
    
    loop_detected_ = false;
    prev_evidence_ = false;
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