CXX = g++
CXXFLAGS = -std=c++20 -Wall -Wextra -O2
INCLUDES = -I/usr/include

TARGET = bin/probe
SRC = src/probe.cpp

all: $(TARGET)

$(TARGET): $(SRC)
	@mkdir -p bin
	$(CXX) $(CXXFLAGS) $(INCLUDES) -o $(TARGET) $(SRC)

clean:
	rm -rf bin

.PHONY: all clean