# Stage 1: Build dependencies
FROM python:3.12 AS builder

# Install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip uninstall -y asyncio || true && \
    pip install --no-cache-dir -r requirements.txt --target /app/dependencies

# Stage 2: Final image
FROM python:3.12-slim

# Install only necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependencies from the builder stage
COPY --from=builder /app/dependencies /app/dependencies

# Ensure Uvicorn is installed globally
RUN pip install --no-cache-dir uvicorn
RUN pip install opentelemetry-distro opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi && opentelemetry-bootstrap -a install
# Install boostrap otel deps


# Copy the application code
COPY . /app

# Update Python path for installed dependencies
ENV PYTHONPATH="/usr/local/lib/python3.12:/app/dependencies:$PYTHONPATH"

ENV LOG_LEVEL="info"
# Command to run the FastAPI app with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8483", "--log-config", "logging_config.yml"]
