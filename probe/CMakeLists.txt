cmake_minimum_required(VERSION 3.10)
project(AetherOS-Probe)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Source files
set(SOURCES
    src/main.cpp
    src/process_monitor.cpp
    src/loop_detector.cpp
    src/system_interceptor.cpp
    src/zmq_communicator.cpp
)

# Headers
set(HEADERS
    include/process_monitor.h
    include/loop_detector.h
    include/system_interceptor.h
    include/zmq_communicator.h
)

# Add executable
add_executable(aetheros-probe ${SOURCES} ${HEADERS})

# Include directories
target_include_directories(aetheros-probe PRIVATE include)

# Link libraries
set(LINK_LIBS pthread)

# -------------------------------------------------
# ZMQ support – use pkg-config if available
# -------------------------------------------------
find_package(PkgConfig QUIET)
if(PKG_CONFIG_FOUND)
    pkg_check_modules(ZMQ REQUIRED libzmq)
    if(ZMQ_FOUND)
        target_include_directories(aetheros-probe PRIVATE ${ZMQ_INCLUDE_DIRS})
        list(APPEND LINK_LIBS ${ZMQ_LIBRARIES})
        target_compile_definitions(aetheros-probe PRIVATE HAVE_ZMQ)
        message(STATUS "ZMQ found via pkg-config")
    else()
        message(WARNING "pkg-config found but zmq module not available")
    endif()
else()
    message(WARNING "PkgConfig not found – building without ZMQ support")
endif()
# -------------------------------------------------

# Link all libraries
target_link_libraries(aetheros-probe ${LINK_LIBS})

# Compiler options
target_compile_options(aetheros-probe PRIVATE -Wall -Wextra -Wpedantic)
