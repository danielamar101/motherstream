# OBS Stability Improvements

This document outlines the improvements made to prevent OBS crashes during stream switching events and maintain a stable connection to the OBS WebSocket.

## Problem

OBS sometimes crashes during stream switch events when multiple WebSocket commands are sent in rapid succession. This disrupts the streaming state and requires manual intervention.

## Solutions Implemented

### 1. Sequential Job Delays

**What it does:** Adds configurable delays between OBS WebSocket operations to prevent overwhelming OBS with rapid commands.

**How it works:**
- Tracks the timestamp of the last OBS-related job execution
- Enforces a minimum delay (default: 2 seconds) between OBS operations
- Only affects OBS-specific jobs (`TOGGLE_OBS_SRC`, `RESTART_MEDIA_SOURCE`)

**Configuration:**
- Default delay: 2.0 seconds
- Configurable via API endpoint: `POST /debug/update-obs-job-delay`
- Valid range: 0.5 - 10.0 seconds

### 2. Connection Health Monitoring

**What it does:** Continuously monitors the OBS WebSocket connection and automatically reconnects when issues are detected.

**How it works:**
- Background thread performs periodic health checks (default: every 30 seconds)
- Uses `GetVersion` request as a lightweight health check
- Implements exponential backoff for reconnection attempts
- Automatically marks connection as unhealthy when errors occur

**Features:**
- **Periodic Health Checks:** Regular connection validation
- **Automatic Reconnection:** Attempts to reconnect when connection fails
- **Exponential Backoff:** Prevents rapid reconnection attempts
- **Connection State Tracking:** Maintains awareness of connection health
- **Graceful Error Handling:** Continues operation even when OBS is temporarily unavailable

## API Endpoints

### Connection Health Monitoring

#### Get Connection Health Status
```http
GET /obs/connection-health
```
Returns the current health status of the OBS WebSocket connection.

#### Force Reconnection
```http
POST /obs/force-reconnect
```
Manually trigger a reconnection attempt to OBS.

#### Get Health Monitor Configuration
```http
GET /debug/obs-health-monitor-config
```
Returns current health monitoring settings.

#### Update Health Monitor Configuration
```http
POST /debug/update-obs-health-monitor-config
```
Parameters:
- `health_check_interval`: Seconds between health checks (10-300)
- `max_reconnect_attempts`: Maximum reconnection attempts (1-20)
- `reconnect_delay`: Initial reconnection delay in seconds (1-60)

### Job Delay Configuration

#### Get Job Delay Configuration
```http
GET /debug/obs-job-delay-config
```
Returns current OBS job delay settings and timing information.

#### Update Job Delay
```http
POST /debug/update-obs-job-delay
```
Parameters:
- `delay_seconds`: New delay in seconds (0.5-10.0)

## Configuration Options

### Health Monitoring Settings
- **Health Check Interval:** 30 seconds (configurable: 10-300s)
- **Max Reconnect Attempts:** 5 (configurable: 1-20)
- **Reconnect Delay:** 5 seconds initial, with exponential backoff (configurable: 1-60s)

### Job Delay Settings
- **OBS Job Delay:** 2.0 seconds (configurable: 0.5-10.0s)

## Benefits

1. **Reduced OBS Crashes:** Sequential job delays prevent overwhelming OBS with rapid commands
2. **Automatic Recovery:** Health monitoring ensures connection issues are detected and resolved automatically
3. **Better Reliability:** Stream switching operations are more stable and predictable
4. **Monitoring Capabilities:** Real-time visibility into connection health and job timing
5. **Configurable:** Settings can be adjusted based on your OBS setup and requirements

## Usage Examples

### Check if OBS connection is healthy
```bash
curl http://localhost:8000/obs/connection-health
```

### Force a reconnection if having issues
```bash
curl -X POST http://localhost:8000/obs/force-reconnect
```

### Increase delay between OBS jobs if still experiencing crashes
```bash
curl -X POST "http://localhost:8000/debug/update-obs-job-delay?delay_seconds=3.0"
```

### Adjust health check frequency
```bash
curl -X POST "http://localhost:8000/debug/update-obs-health-monitor-config?health_check_interval=60"
```

## Monitoring

The system logs provide detailed information about:
- OBS job delays and timing
- Connection health check results
- Reconnection attempts and outcomes
- Configuration changes

Look for log entries from:
- `app.obs` - OBS connection and operations
- `app.core.worker` - Job processing and delays
- `OBSHealthMonitor` - Health monitoring thread

## Troubleshooting

### If OBS still crashes frequently:
1. Increase the job delay: `POST /debug/update-obs-job-delay?delay_seconds=5.0`
2. Check OBS logs for specific error patterns
3. Verify OBS WebSocket plugin is up to date

### If connection keeps dropping:
1. Check OBS WebSocket server settings
2. Verify network connectivity
3. Increase reconnection attempts: `POST /debug/update-obs-health-monitor-config?max_reconnect_attempts=10`

### If health checks are too frequent:
1. Increase health check interval: `POST /debug/update-obs-health-monitor-config?health_check_interval=60` 