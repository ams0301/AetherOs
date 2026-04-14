#include <iostream>
#include <fstream>
#include <string>
#include <deque>
#include <vector>
#include <map>
#include <unistd.h> // for sleep
#include <sys/stat.h> // for stat
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <cctype>
#include <regex>

std::string extractCommand(const std::string& line) {
    // Expected format: [exec] <command>
    // We'll look for the pattern [exec] and take everything after it
    std::smatch match;
    std::regex pattern(R"(\[exec\]\s*(.+))");
    if (std::regex_search(line, match, pattern)) {
        return match[1].str();
    }
    // If not found, return the whole line (or empty?)
    return line;
}

std::string trim(const std::string& str) {
    size_t first = str.find_first_not_of(" \t\n\r");
    if (first == std::string::npos)
        return "";
    size_t last = str.find_last_not_of(" \t\n\r");
    return str.substr(first, (last - first + 1));
}

int main(int argc, char* argv[]) {
    if (argc < 4) {
        std::cerr << "Usage: " << argv[0] << " --log-file <path> --window <size> --threshold <count>" << std::endl;
        return 1;
    }

    std::string logFile;
    int windowSize = 5;
    int threshold = 3;

    for (int i = 1; i < argc; i += 2) {
        std::string arg = argv[i];
        if (arg == "--log-file") {
            logFile = argv[i+1];
        } else if (arg == "--window") {
            windowSize = std::stoi(argv[i+1]);
        } else if (arg == "--threshold") {
            threshold = std::stoi(argv[i+1]);
        }
    }

    std::cout << "Monitoring log file: " << logFile << std::endl;
    std::cout << "Window size: " << windowSize << ", Threshold: " << threshold << std::endl;

    // Open the log file and seek to the end
    std::ifstream logStream(logFile, std::ios::in);
    if (!logStream.is_open()) {
        std::cerr << "Error: Could not open log file: " << logFile << std::endl;
        return 1;
    }
    logStream.seekg(0, std::ios::end);
    std::streampos lastPos = logStream.tellg();

    // State for loop detection
    std::deque<std::string> commandWindow;
    std::map<std::vector<std::string>, int> stateCountMap;

    while (true) {
        // Sleep for 1 second to avoid busy waiting
        sleep(1);

        // Check current size of the file
        struct stat fileStat;
        if (stat(logFile.c_str(), &fileStat) != 0) {
            perror("stat");
            continue;
        }
        std::streampos currentSize = fileStat.st_size;

        if (currentSize > lastPos) {
            // There is new data to read
            logStream.seekg(lastPos);
            std::string line;
            while (std::getline(logStream, line)) {
                std::cerr << "DEBUG: Read line: '" << line << "'" << std::endl;
                std::string command = extractCommand(line);
                command = trim(command);
                if (!command.empty()) {
                    std::cerr << "DEBUG: Extracted command: '" << command << "'" << std::endl;
                    // Add to window
                    commandWindow.push_back(command);
                    if (commandWindow.size() > static_cast<size_t>(windowSize)) {
                        commandWindow.pop_front();
                    }

                    // Debug: print current window
                    std::cerr << "DEBUG: WINDOW: [";
                    for (size_t j = 0; j < commandWindow.size(); ++j) {
                        std::cerr << commandWindow[j];
                        if (j < commandWindow.size()-1) std::cerr << ", ";
                    }
                    std::cerr << "]" << std::endl;

                    // If we have a full window, check for loop
                    if (commandWindow.size() == static_cast<size_t>(windowSize)) {
                        std::vector<std::string> state(commandWindow.begin(), commandWindow.end());
                        auto it = stateCountMap.find(state);
                        if (it != stateCountMap.end()) {
                            it->second++;
                            std::cerr << "DEBUG: State seen " << it->second << " times" << std::endl;
                            if (it->second >= threshold) {
                                std::cout << "🚨 LOOP DETECTED: Last " << windowSize 
                                          << " commands repeated " << it->second << " times:" << std::endl;
                                for (const auto& cmd : state) {
                                    std::cout << "  - " << cmd << std::endl;
                                }
                                // Reset count to avoid continuous alerts for the same loop
                                it->second = 0;
                            }
                        } else {
                            stateCountMap[state] = 1;
                            std::cerr << "DEBUG: New state added to map" << std::endl;
                        }
                    }
                }
            }
            lastPos = logStream.tellg();
            std::cerr << "DEBUG: Updated lastPos to " << lastPos << std::endl;
        }
    }

    return 0;
}