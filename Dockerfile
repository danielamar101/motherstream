# Use Debian-based Python image
FROM python:3.12 AS builder

# Update package list and install build dependencies including Rust for shazamio-core
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libffi-dev \
    libpq-dev \
    python3-dev \
    curl \
    build-essential \
    libssl-dev \
    pkg-config \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && . $HOME/.cargo/env \
    && rm -rf /var/lib/apt/lists/*

# Add Rust to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --target /app/dependencies

# Final stage
FROM python:3.12

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -g 1001 appgroup && \
    useradd -r -u 1001 -g appgroup -d /app -s /sbin/nologin -c "App User" appuser

# Set working directory
WORKDIR /app

# Copy dependencies from builder stage
COPY --from=builder /app/dependencies /app/dependencies

# Install uvicorn and OpenTelemetry packages in a single layer
RUN pip install --no-cache-dir \
    uvicorn \
    opentelemetry-distro \
    opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-fastapi && \
    opentelemetry-bootstrap -a install && \
    pip cache purge

# Copy application code
COPY . /app

# Set ownership and permissions
RUN chown -R appuser:appgroup /app

# Update Python path for installed dependencies
ENV PYTHONPATH="/usr/local/lib/python3.12:/app/dependencies:$PYTHONPATH" \
    LOG_LEVEL="info" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8483

# Command to run the FastAPI app with Uvicorn and custom logging config
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8483", "--log-config", "logging_config.yml"]
