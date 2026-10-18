#ifndef LOOP_DETECTOR_H
#define LOOP_DETECTOR_H

#include <string>
#include <vector>
#include <cstdint>
#include <unordered_map>
#include <chrono>

namespace aetheros {
namespace probe {

struct ProcessFeatures {
    double cpu_usage;
    double memory_mb;
    double disk_read_kb;
    double disk_write_kb;
    long long timestamp;
};

class LoopDetector {
public:
    LoopDetector(size_t window_size = 20, double similarity_threshold = 0.85, 
                 size_t min_matches_for_alert = 3);
    ~LoopDetector();
    
    // Add a new process feature sample
    void addFeatureSample(const ProcessFeatures& features);
    
    // Check if a loop has been detected
    bool isLoopDetected() const;
    
    // Get confidence score of loop detection (0.0 to 1.0)
    double getLoopConfidence() const;
    
    // Get details about detected loop
    std::string getLoopDetails() const;
    
    // Reset the detector
    void reset();
    
    // Update sensitivity settings
    void setSimilarityThreshold(double threshold);
    void setWindowSize(size_t size);
    
private:
    // Calculate similarity between two feature vectors (0.0 to 1.0)
    double calculateSimilarity(const ProcessFeatures& f1, const ProcessFeatures& f2) const;

    size_t window_size_;
    double similarity_threshold_;
    size_t min_matches_for_alert_;

    std::vector<ProcessFeatures> feature_window_;
    std::vector<bool> match_flags_;  // Tracks which samples matched others
    size_t pos_;  // Current position in circular buffer

    bool loop_detected_;
    double confidence_;
    std::string loop_details_;

    // Consecutive-evidence confirmation: a detection requires sufficient
    // matches on two consecutive samples (Poisson spikes are independent,
    // real loops persist)
    bool prev_evidence_ = false;
};

} // namespace probe
} // namespace aetheros

#endif // LOOP_DETECTOR_H