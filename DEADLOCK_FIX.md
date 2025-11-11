# Stream Health Check Deadlock Fix

## Problem Summary

After a stress test with 5 users, a resource starvation issue was observed where `CHECK_STREAM_HEALTH` jobs piled up in the worker queue, causing wait times to grow from 117s to 145s and beyond.

## Root Cause

The issue was caused by a rate mismatch between job creation and execution:

1. **Job Creation Rate**: Every 3 seconds, the `process_queue()` loop in `process_manager.py` (line 331-334) queues a new `CHECK_STREAM_HEALTH` job when there's an active lead stream.

2. **Job Execution Time**: Each health check took ~10 seconds to complete (due to ffprobe timeout).

3. **Result**: Jobs were queued 3x faster than they could be processed (3s interval vs 10s execution), causing exponential backlog.

## Observed Symptoms

From the logs:
```
Job queue contains 67 jobs
waited 117797.84ms  (117s)
waited 124815.09ms  (124s)
waited 131832.69ms  (131s)
waited 138850.72ms  (138s)
waited 145868.61ms  (145s)
```

Each subsequent health check waited ~7 seconds longer than the previous one, showing clear queue buildup.

## The Fix

Three changes were made to `app/core/stream_health_checker.py`:

### 1. Added Concurrency Control Flag
```python
self.is_checking = False  # Flag to prevent concurrent health checks
```

### 2. Check-and-Skip Logic
Added early return if a health check is already in progress:
```python
with self.lock:
    if self.is_checking:
        logger.debug(f"Health check already in progress for {self.stream_url}, skipping")
        return self.is_healthy
    self.is_checking = True
```

### 3. Reduced ffprobe Timeout
Changed timeout from 10 seconds to 3 seconds:
```python
timeout=3  # Reduced from 10s to 3s for faster failure detection
```

### 4. Cleanup in Finally Block
Ensures the flag is always cleared:
```python
finally:
    with self.lock:
        self.is_checking = False
```

## Benefits

1. **No More Queue Buildup**: Only one health check can be in flight at a time
2. **Faster Failure Detection**: 3-second timeout instead of 10 seconds
3. **Thread-Safe**: Uses existing lock mechanism to prevent race conditions
4. **Graceful Degradation**: If a check is in progress, subsequent requests just return the current health status

## Testing Recommendations

1. Run the same 5-user stress test that exposed the issue
2. Monitor the job queue size - it should stay small (< 10 jobs typically)
3. Check health check wait times - should be minimal (<1s in most cases)
4. Verify health checks still properly detect stream failures

## Expected Behavior After Fix

- Health checks queue every 3 seconds
- If previous check is still running, new requests skip immediately
- Queue should never build up with more than a handful of health check jobs
- Worker remains responsive to other job types (TOGGLE_OBS_SRC, etc.)

