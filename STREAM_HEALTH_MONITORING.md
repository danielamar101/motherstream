# Stream Health Monitoring Implementation

## Overview

This implementation adds robust health monitoring for the RTMP output stream at `rtmp://127.0.0.1:1935/motherstream/live`. The system automatically detects when the output stream becomes unhealthy and takes corrective action by dropping the current stream publisher after 30 seconds of continuous unhealthy state.

## Problem Solved

Previously, the system could get into a state where it believed there was an active stream, but the actual RTMP output stream was not functioning. This would cause the system to sit indefinitely without any corrective action, leading to a mismatch between internal state and actual stream status.

## Implementation Details

### 1. StreamHealthChecker Class (`app/core/stream_health_checker.py`)

A new class that monitors RTMP stream health using `ffprobe`:

- **Health Check Method**: Uses `ffprobe` to probe the RTMP stream and verify it's accessible
- **Failure Tracking**: Tracks the first failure time and calculates unhealthy duration
- **Thread Safety**: Uses threading locks to ensure safe concurrent access
- **Configurable Threshold**: Default 30-second threshold before considering stream failed

#### Key Methods:
- `check_stream_health()`: Performs health check using ffprobe
- `is_unhealthy_for_threshold()`: Returns True if stream has been unhealthy for too long
- `get_unhealthy_duration()`: Returns how long stream has been unhealthy
- `reset()`: Resets health checker state (called when streams switch)

### 2. Worker Integration (`app/core/worker.py`)

Added new job type `CHECK_STREAM_HEALTH` to the worker system:

- **Non-blocking**: Health checks run in the background worker thread
- **Integrated Dispatch**: Handles health check jobs and logs results
- **Error Handling**: Gracefully handles health check failures

### 3. Process Manager Integration (`app/core/process_manager.py`)

Integrated health monitoring into the main stream management loop:

- **Automatic Monitoring**: Health checks are queued every 3 seconds when a stream is active
- **Threshold Detection**: Automatically detects when threshold is exceeded
- **Corrective Action**: Drops publisher and sends Discord notification when stream is unhealthy
- **State Management**: Resets health checker when streams start/switch

#### Key Methods Added:
- `handle_unhealthy_stream()`: Handles the corrective action when stream is unhealthy for too long

## How It Works

1. **Continuous Monitoring**: When there's an active stream, the system queues health check jobs every 3 seconds
2. **Health Detection**: Each health check uses `ffprobe` to verify the RTMP stream is accessible
3. **Failure Tracking**: If health checks fail, the system tracks how long the stream has been unhealthy
4. **Threshold Action**: After 30 seconds of continuous failure, the system:
   - Logs an error message
   - Sends a Discord notification about the issue
   - Drops the current stream publisher (kicks them)
   - Resets the health checker state
5. **Recovery**: The kicked publisher can reconnect, or the system will switch to the next streamer in queue

## Configuration

- **Stream URL**: `rtmp://127.0.0.1:1935/motherstream/live` (the output stream)
- **Unhealthy Threshold**: 30 seconds
- **Check Frequency**: Every 3 seconds (when stream is active)
- **ffprobe Timeout**: 10 seconds per check

## Benefits

1. **Automatic Recovery**: No manual intervention needed when streams become unhealthy
2. **State Consistency**: Ensures internal state matches actual stream status
3. **User Notification**: Discord alerts inform administrators of issues
4. **Minimal Impact**: Health checks run in background without blocking main operations
5. **Robust Detection**: Uses industry-standard `ffprobe` for reliable stream detection

## Dependencies

- **ffprobe**: Already available in the Docker container via ffmpeg package
- **subprocess**: Python standard library for running ffprobe commands
- **threading**: For thread-safe operation

## Logging

The system provides detailed logging at different levels:

- **INFO**: Stream recovery messages
- **WARNING**: Health check failures and timeout notifications
- **ERROR**: Stream unhealthy for threshold duration
- **DEBUG**: Individual health check results

## Testing

The implementation has been tested with:
- Non-existent streams (correctly detected as unhealthy)
- Threshold mechanism (correctly triggers after configured time)
- Reset functionality (correctly resets state)
- Integration with existing worker and process manager systems

## Future Enhancements

Potential improvements could include:
- Configurable health check frequency
- Different thresholds for different types of failures
- Health check metrics and statistics
- Alternative stream probing methods
- Gradual backoff for health check frequency 