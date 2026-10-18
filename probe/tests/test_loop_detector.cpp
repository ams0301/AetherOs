#include "loop_detector.h"
#include <cstdio>
#include <functional>
#include <random>
#include <string>
#include <vector>

using aetheros::probe::LoopDetector;
using aetheros::probe::ProcessFeatures;

static int g_failures = 0;

static ProcessFeatures makeSample(double cpu, double mem, double dr, double dw, long long t) {
    ProcessFeatures f{};
    f.cpu_usage = cpu;
    f.memory_mb = mem;
    f.disk_read_kb = dr;
    f.disk_write_kb = dw;
    f.timestamp = t;
    return f;
}

struct RunResult {
    int detections = 0;
    long long first_detection_sample = -1;
};

static RunResult feedSeries(LoopDetector& d, const std::vector<ProcessFeatures>& samples) {
    RunResult r;
    for (size_t i = 0; i < samples.size(); ++i) {
        d.addFeatureSample(samples[i]);
        if (d.isLoopDetected()) {
            r.detections++;
            if (r.first_detection_sample < 0) {
                r.first_detection_sample = static_cast<long long>(i + 1);
            }
            d.reset();
        }
    }
    return r;
}

static std::vector<ProcessFeatures> generate(
    size_t count,
    std::function<ProcessFeatures(long long)> gen) {
    std::vector<ProcessFeatures> v;
    v.reserve(count);
    for (long long t = 1; t <= static_cast<long long>(count); ++t) {
        v.push_back(gen(t));
    }
    return v;
}

static void expect(const std::string& name, const RunResult& r,
                   int min_detections, int max_detections) {
    bool pass = (r.detections >= min_detections) && (r.detections <= max_detections);
    std::printf("  %-22s detections=%-3d first_at_sample=%-3lld  %s\n",
                name.c_str(), r.detections, r.first_detection_sample,
                pass ? "PASS" : "FAIL");
    if (!pass) g_failures++;
}

int main() {
    std::printf("Loop detector adversarial test suite\n");
    std::printf("(window=15, threshold=0.8, min_matches=3 -> required=max(3,5)=5,\n");
    std::printf(" per-dim deadbands: cpu 5%% / mem 4MB / disk 512KB, consecutive-confirm)\n\n");

    {
        LoopDetector d(15, 0.8, 3);
        auto samples = generate(60, [](long long) {
            return makeSample(0.0, 3.25, 0.0, 0.0, 0);
        });
        std::printf("Case 1: idle flat process (cpu=0.0, mem const, no I/O)\n");
        std::printf("  expected: 0 detections (activity gate suppresses idle)\n");
        expect("idle_flat", feedSeries(d, samples), 0, 0);
    }

    {
        LoopDetector d(15, 0.8, 3);
        auto samples = generate(60, [](long long) {
            return makeSample(99.5, 3.25, 0.0, 0.0, 0);
        });
        std::printf("Case 2: pinned-CPU spin loop (cpu=99.5 const) [flagship TP]\n");
        std::printf("  expected: >=1 detection, first at sample 7 (5 stored + 1 confirm)\n");
        expect("spin_flat", feedSeries(d, samples), 1, 100);
    }

    {
        LoopDetector d(15, 0.8, 3);
        std::mt19937 rng(42);
        std::uniform_real_distribution<double> jitter(-0.5, 0.5);
        auto samples = generate(100, [&](long long) {
            return makeSample(99.5 + jitter(rng), 3.25, 0.0, 0.0, 0);
        });
        std::printf("Case 3: spin loop with +-0.5%% CPU jitter (within deadband)\n");
        std::printf("  expected: >=1 detection\n");
        expect("spin_jitter", feedSeries(d, samples), 1, 100);
    }

    {
        LoopDetector d(15, 0.8, 3);
        std::mt19937 rng(7);
        std::uniform_real_distribution<double> cpu(0.0, 2.0);
        std::uniform_real_distribution<double> mem(30.0, 30.05);
        auto samples = generate(200, [&](long long) {
            return makeSample(cpu(rng), mem(rng), 0.0, 0.0, 0);
        });
        std::printf("Case 4: light randomized work (cpu U[0,2]%%, mem 30+-0.05MB)\n");
        std::printf("  expected: 0 detections (below activity floor: original FP repro)\n");
        expect("light_random", feedSeries(d, samples), 0, 0);
    }

    {
        LoopDetector d(15, 0.8, 3);
        std::mt19937 rng(1234);
        std::uniform_real_distribution<double> cpu(0.0, 50.0);
        std::uniform_real_distribution<double> mem(28.0, 32.0);
        std::uniform_real_distribution<double> rate(0.0, 2000.0);
        auto samples = generate(300, [&](long long) {
            return makeSample(cpu(rng), mem(rng), rate(rng), rate(rng), 0);
        });
        std::printf("Case 5: heavy randomized work (cpu U[0,50]%%, mem U[28,32]MB, I/O rates)\n");
        std::printf("  expected: 0 detections (active but never similar)\n");
        expect("heavy_random", feedSeries(d, samples), 0, 0);
    }

    {
        LoopDetector d(15, 0.8, 3);
        auto samples = generate(60, [](long long t) {
            double cpu = ((t - 1) % 2 == 0) ? 10.0 : 40.0;
            return makeSample(cpu, 30.0, 0.0, 0.0, t);
        });
        std::printf("Case 6: active period-2 pattern (cpu 10 <-> 40)\n");
        std::printf("  expected: >=1 detection (same-phase samples match)\n");
        expect("periodic2_active", feedSeries(d, samples), 1, 100);
    }

    {
        LoopDetector d(15, 0.8, 3);
        auto samples = generate(90, [](long long t) {
            static const double cycle[3] = {10.0, 40.0, 25.0};
            return makeSample(cycle[(t - 1) % 3], 30.0, 0.0, 0.0, t);
        });
        std::printf("Case 7: active period-3 pattern (documented limitation)\n");
        std::printf("  expected: 0 (max 4 same-phase in window < required 5)\n");
        expect("periodic3_active", feedSeries(d, samples), 0, 0);
    }

    {
        LoopDetector d(15, 0.8, 3);
        auto samples = generate(60, [](long long t) {
            double mem = 30.0 + 0.1 * static_cast<double>(t);
            return makeSample(50.0, mem, 0.0, 0.0, t);
        });
        std::printf("Case 8: slow memory-drift loop (+0.1MB/sample, cpu 50 const)\n");
        std::printf("  expected: >=1 detection (drift within deadband horizon)\n");
        expect("drift_slow", feedSeries(d, samples), 1, 100);
    }

    {
        LoopDetector d(15, 0.8, 3);
        auto samples = generate(60, [](long long t) {
            double mem = 30.0 + 1.0 * static_cast<double>(t);
            return makeSample(50.0, mem, 0.0, 0.0, t);
        });
        std::printf("Case 9: fast memory drift (+1.0MB/sample) [documented boundary]\n");
        std::printf("  expected: 0 (drift exceeds deadband within ~1 sample)\n");
        expect("drift_fast", feedSeries(d, samples), 0, 0);
    }

    {
        LoopDetector d(15, 0.8, 3);
        std::mt19937 rng(99);
        std::uniform_real_distribution<double> cpu(70.0, 90.0);
        auto samples = generate(200, [&](long long) {
            return makeSample(cpu(rng), 3.25, 0.0, 0.0, 0);
        });
        std::printf("Case 10: random work INSIDE active band (cpu U[70,90]%%, all else flat)\n");
        std::printf("  expected: 0 (wobble exceeds 5%% deadband; spikes need 2 consecutive)\n");
        expect("active_band_random", feedSeries(d, samples), 0, 0);
    }

    {
        LoopDetector d(15, 0.8, 3);
        std::mt19937 rng(5);
        std::uniform_real_distribution<double> jitter(-40.0, 40.0);
        auto samples = generate(80, [&](long long) {
            return makeSample(2.0, 30.0, 512.0 + jitter(rng), 0.0, 0);
        });
        std::printf("Case 11: constant-rate I/O loop (rate 512+-40KB/sample, cpu 2%%)\n");
        std::printf("  expected: >=1 detection (activity via I/O; rate jitter within deadband)\n");
        expect("disk_rate_loop", feedSeries(d, samples), 1, 100);
    }

    {
        LoopDetector d(15, 0.8, 3);
        std::mt19937 rng(11);
        std::uniform_real_distribution<double> rate(0.0, 5000.0);
        auto samples = generate(200, [&](long long) {
            return makeSample(2.0, 30.0, rate(rng), 0.0, 0);
        });
        std::printf("Case 12: random I/O rates (U[0,5000]KB/sample, cpu 2%%)\n");
        std::printf("  expected: 0 (active via I/O but rates never similar)\n");
        expect("disk_rate_random", feedSeries(d, samples), 0, 0);
    }

    std::printf("\n%s (%d failure(s))\n",
                g_failures == 0 ? "ALL CASES PASSED" : "SOME CASES FAILED", g_failures);
    return g_failures == 0 ? 0 : 1;
}