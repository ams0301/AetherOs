# Aether-OS Dockerfile
# Multi-stage build for Probe (C++), Auditor (Python), and Controller (Python)

# ======================
# BUILD STAGE FOR PROBE
# ======================
FROM ubuntu:22.04 AS probe-builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy probe source code
COPY probe/ ./probe/

# Build probe
RUN mkdir -p probe/build && \
    cd probe/build && \
    cmake .. && \
    make

# ======================
# BUILD STAGE FOR AUDITOR
# ======================
FROM python:3.10-slim AS auditor-builder

# Install auditor dependencies
WORKDIR /app
COPY auditor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy auditor source
COPY auditor/src/ ./auditor/src/

# ======================
# BUILD STAGE FOR CONTROLLER
# ======================
FROM python:3.10-slim AS controller-builder

# Install controller dependencies
WORKDIR /app
COPY controller/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy controller source
COPY controller/src/ ./controller/src/

# ======================
# FINAL STAGE
# ======================
FROM ubuntu:22.04

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libstdc++6 \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy built probe
COPY --from=probe-builder /app/probe/build/aetheros-probe ./probe/

# Copy auditor dependencies and code
COPY --from=auditor-builder /usr/local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/site-packages/
COPY --from=auditor-builder /app/auditor/src/ ./auditor/

# Copy controller dependencies and code
COPY --from=controller-builder /usr/local/lib/python3.10-site-packages/ /usr/local/lib/python3.10-site-packages/
COPY --from=controller-builder /app/controller/src/ ./controller/

# Create necessary directories
RUN mkdir -p logs snapshots configs

# Create a non-root user for security
RUN useradd -m -u 1000 aetheros
USER aetheros

# Expose ports (if needed for communication)
# EXPOSE 5555  # ZMQ port for inter-component communication

# Default command - can be overridden
CMD ["./probe/aetheros-probe"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep aetheros-probe >/dev/null || exit 1