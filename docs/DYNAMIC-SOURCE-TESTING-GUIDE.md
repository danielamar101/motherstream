# Dynamic Source Switching - Testing Guide

## Quick Start Testing

### Prerequisites

1. **OBS Running** with obs-gstreamer plugin installed
2. **Scene Named** `MOTHERSTREAM` exists in OBS
3. **RTMP Stream** available at configured host/port
4. **Application Running** (docker-compose or local)

### Test 1: Basic Dynamic Source Creation

Test that a new source can be created and shown:

```bash
# Use the test endpoint
curl -X POST "http://localhost:8000/debug/test-dynamic-source-switch" \
  -H "Content-Type: application/json" \
  -d '{
    "rtmp_url": "rtmp://127.0.0.1:1935/motherstream/live",
    "scene_name": "MOTHERSTREAM"
  }'
```

**Expected Result**:
- Response: `{"status": "success", ...}`
- In OBS: New source `GMOTHERSTREAM_1` appears in scene
- In OBS: Source should be positioned 5 layers below the top (check scene item order)
- In logs: See "Creating new GStreamer source..." → "Setting z-order..." → "Successfully switched..."

### Test 2: Multiple Switches

Test that old sources are cleaned up:

```bash
# First switch
curl -X POST "http://localhost:8000/debug/test-dynamic-source-switch"

# Wait 20 seconds for completion

# Second switch
curl -X POST "http://localhost:8000/debug/test-dynamic-source-switch"

# Wait 20 seconds

# Check that only the latest source exists
curl http://localhost:8000/obs/list-inputs | jq '.inputs[] | select(.inputName | startswith("GMOTHERSTREAM"))'
```

**Expected Result**:
- Only one GMOTHERSTREAM source should exist (highest number)
- Previous sources should be removed

### Test 3: Stream Switch Simulation

Test with actual stream keys:

```bash
# Start a test stream (if you have a streamer)
# Then trigger a switch to that stream

# This would normally happen automatically, but you can test manually:
curl -X POST "http://localhost:8000/debug/test-dynamic-source-switch" \
  -H "Content-Type: application/json" \
  -d '{
    "rtmp_url": "rtmp://127.0.0.1:1935/motherstream/live?stream_key=YOUR_STREAM_KEY",
    "scene_name": "MOTHERSTREAM"
  }'
```

**Expected Result**:
- New source connects to actual stream
- Video/audio plays in OBS
- No frozen frames during transition

### Test 4: Z-Order Configuration

Test adjusting the layer position:

```bash
# Check current z-offset
curl http://localhost:8000/debug/get-source-z-offset

# Change to 3 layers from top
curl -X POST "http://localhost:8000/debug/set-source-z-offset?z_offset=3"

# Create a test source to verify new position
curl -X POST "http://localhost:8000/debug/test-dynamic-source-switch"

# In OBS: Verify the source is now 3 layers from the top instead of 5
```

**Expected Result**:
- Z-offset setting changes successfully
- New sources created after the change use the new position
- Existing sources keep their original position

### Test 5: Failure Handling

Test what happens when stream doesn't exist:

```bash
# Use a fake RTMP URL
curl -X POST "http://localhost:8000/debug/test-dynamic-source-switch" \
  -H "Content-Type: application/json" \
  -d '{
    "rtmp_url": "rtmp://127.0.0.1:1935/nonexistent/fake",
    "scene_name": "MOTHERSTREAM"
  }'
```

**Expected Result**:
- Job enqueues successfully
- After 15s timeout, source is cleaned up
- Logs show: "New source did not become ready within 15.0s"
- No orphaned sources in OBS

## Monitoring During Tests

### Terminal 1: Application Logs

```bash
# If running in Docker
docker logs -f motherstream

# If running locally
tail -f logs/motherstream.log
```

Look for these log patterns:

```
# Successful switch
✓ Creating new GStreamer source 'GMOTHERSTREAM_X'
✓ Waiting for source 'GMOTHERSTREAM_X' to become ready
✓ Source 'GMOTHERSTREAM_X' state: OBS_MEDIA_STATE_PLAYING
✓ Source 'GMOTHERSTREAM_X' is PLAYING after X.XXs
✓ Successfully switched to new source 'GMOTHERSTREAM_X'
✓ Cleaned up old source 'GMOTHERSTREAM_Y'

# Failed switch
✗ Failed to create GStreamer source 'GMOTHERSTREAM_X'
✗ New source 'GMOTHERSTREAM_X' did not become ready within 15.0s
```

### Terminal 2: OBS Source Monitoring (Optional)

If you want detailed OBS monitoring:

```bash
cd tests/e2e
python3 obs-stream-switch-monitor.py --poll-interval 0.3
```

This will track source state changes in real-time.

### Terminal 3: OBS WebSocket Calls (Debug)

Watch raw OBS WebSocket activity:

```bash
# List all inputs
watch -n 2 'curl -s http://localhost:8000/obs/list-inputs | jq ".inputs[] | select(.inputName | startswith(\"GMOTHERSTREAM\"))"'
```

## Integration Test with Real Streams

### Setup

1. Have 2+ test accounts with stream keys
2. Add them to the queue using the web UI or API
3. Let them start streaming

### Test Flow

1. **First Stream Starts**: `GMOTHERSTREAM_1` created and shown
2. **Second Stream Queued**: Waits in queue
3. **First Stream Times Out or Switches**: 
   - `GMOTHERSTREAM_1` hidden
   - `GMOTHERSTREAM_2` created with second stream's URL
   - Wait for PLAYING state
   - `GMOTHERSTREAM_2` shown
   - `GMOTHERSTREAM_1` removed

### What to Watch For

**Good Signs**:
- ✓ Smooth transition between sources
- ✓ No frozen frames
- ✓ Audio/video in sync
- ✓ Old sources cleaned up
- ✓ Source counter increments correctly

**Bad Signs**:
- ✗ Sources accumulating in OBS
- ✗ Long delays (>15s) during switches
- ✗ Frozen frames still appearing
- ✗ Timestamp issues persist
- ✗ OBS crashes during switch

## Automated E2E Tests

Use the existing test suite with monitoring:

```bash
# Run orderly scenario (recommended for initial testing)
./tests/e2e/run-monitored-test.sh orderly

# Check the monitoring report
cat logs/obs-monitor-*-report.txt
```

Look for:
- **Problematic Transitions**: Should be 0 or very low
- **Source becomes visible while**: Should see "PLAYING" not "BUFFERING"

## Rollback Test

If issues arise, test the rollback:

1. **Comment out dynamic source code** in `process_manager.py` (lines 92-111)
2. **Uncomment old restart code**:
```python
add_job(JobType.RESTART_MEDIA_SOURCE, payload={"source_name": "GMOTHERSTREAM"})
add_job(JobType.TOGGLE_OBS_SRC, payload={"source_name": "GMOTHERSTREAM", "only_off": False})
```
3. **Restart application**
4. **Manually create static source** in OBS named `GMOTHERSTREAM`
5. **Test stream switch** - should work with old behavior

## Performance Testing

### Measure Switch Time

Add timing to logs or use monitoring:

```bash
# Look for these timings in logs
grep "is PLAYING after" logs/motherstream.log

# Typical results:
# Good: 3-7 seconds
# Acceptable: 7-12 seconds
# Slow: >12 seconds (investigate network/stream issues)
```

### Check Resource Usage

```bash
# Monitor OBS CPU/Memory during switch
top -p $(pgrep obs)

# Monitor Docker container resources
docker stats motherstream
```

## Troubleshooting Common Issues

### Issue: "Input kind not found"

**Cause**: obs-gstreamer plugin not installed

**Fix**: Install plugin, restart OBS

### Issue: Sources never become PLAYING

**Cause**: Stream not actually publishing or network issue

**Debug**:
```bash
# Test RTMP connectivity directly
ffplay rtmp://127.0.0.1:1935/motherstream/live

# Check SRS/Oryx status
curl http://localhost:1985/api/v1/streams
```

### Issue: Old sources not cleaning up

**Cause**: Exception during cleanup or OBS WebSocket timeout

**Fix**:
```bash
# Manual cleanup via API
curl -X POST "http://localhost:8000/obs/remove-input?input_name=GMOTHERSTREAM_1"
```

### Issue: OBS crashes during switch

**Cause**: Too many rapid switches, OBS instability

**Fix**: 
- Increase `OBS_JOB_DELAY` in `worker.py`
- Check OBS version compatibility
- Reduce switch frequency

## Success Criteria

The implementation is successful if:

1. ✓ No frozen frames during stream switches
2. ✓ Timestamp inconsistencies resolved
3. ✓ Sources properly cleaned up
4. ✓ Switch completes in <15 seconds
5. ✓ No OBS crashes
6. ✓ Monitoring shows sources PLAYING before visible
7. ✓ Works consistently across multiple switches

## Next Steps After Testing

If tests pass:
1. Deploy to staging environment
2. Monitor production logs for issues
3. Gather metrics on switch times
4. Consider optimizations (pre-creation, pooling)

If tests fail:
1. Review failure logs
2. Check OBS compatibility
3. Verify obs-gstreamer plugin
4. Consider rollback to old approach
5. Report issues with detailed logs

## Getting Help

Include this info when reporting issues:

```bash
# System info
obs --version
python3 --version

# OBS logs (last 100 lines)
tail -100 ~/.config/obs-studio/logs/$(ls -t ~/.config/obs-studio/logs/ | head -1)

# Application logs (relevant portion)
grep -A 20 "SWITCH_GSTREAMER_SOURCE" logs/motherstream.log

# Current OBS sources
curl -s http://localhost:8000/obs/list-inputs | jq '.inputs[] | {name: .inputName, kind: .inputKind}'
```

