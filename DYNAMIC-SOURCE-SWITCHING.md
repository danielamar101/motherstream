# Dynamic GStreamer Source Creation for Stream Switching

## Overview

This document describes the new dynamic source creation approach for handling stream switches in OBS. Instead of restarting a single GStreamer source, we now create fresh sources for each stream switch.

## Problem Solved

### Before (Old Approach)
1. **Frozen Frames**: Media source became visible before fully buffered (PLAYING state)
2. **Timestamp Inconsistencies**: When switching streams, timestamps from previous stream carried over
3. **Unreliable Timing**: No way to know when source was actually ready to display

### After (New Approach)
1. **No Frozen Frames**: Source is buffered while hidden, only shown when in PLAYING state
2. **Clean Timestamps**: Each stream gets a fresh source with its own timestamp context
3. **Reliable Ready State**: We poll `GetMediaInputStatus` until `mediaState == PLAYING`

## How It Works

### Source Lifecycle

```
Stream 1 Active (GMOTHERSTREAM_1)
    ↓
New Stream Arrives
    ↓
Create GMOTHERSTREAM_2 (hidden)
    ↓
Wait for PLAYING state (polling)
    ↓
Hide GMOTHERSTREAM_1
    ↓
Show GMOTHERSTREAM_2
    ↓
Delete GMOTHERSTREAM_1
    ↓
Stream 2 Active (GMOTHERSTREAM_2)
```

### Key Components

#### 1. OBS Methods (`app/obs.py`)

- **`create_gstreamer_source()`** - Creates new source with RTMP URL
- **`wait_for_source_ready()`** - Polls until source is in PLAYING state
- **`switch_to_new_gstreamer_source()`** - Orchestrates the full switch
- **`remove_source()`** - Cleans up old sources
- **`_set_source_visibility()`** - Directly sets visibility without toggling

#### 2. Job System (`app/core/worker.py`)

- **New Job Type**: `SWITCH_GSTREAMER_SOURCE`
- **Payload**: `{"rtmp_url": str, "scene_name": str}`
- **OBS Delay**: Respects the 2-second OBS job delay to prevent crashes

#### 3. Stream Manager (`app/core/process_manager.py`)

- **`start_stream()`** - Now uses `SWITCH_GSTREAMER_SOURCE` instead of `RESTART_MEDIA_SOURCE`
- **RTMP URL Construction**: Builds URL with stream key: `rtmp://HOST:PORT/motherstream/live?stream_key=KEY`

## Configuration

### GStreamer Pipeline

The pipeline is optimized to handle timestamp sync issues and normalize resolution:

```python
gstreamer_pipeline = (
    f"rtmpsrc location={rtmp_url} do-timestamp=true ! "
    "decodebin name=d "
    # Video path
    "d. ! queue max-size-buffers=3 leaky=downstream ! "
    "videoscale ! video/x-raw,width=1920,height=1080 ! "
    "videoconvert ! clocksync ! video.sink "
    # Audio path
    "d. ! queue max-size-buffers=200 leaky=downstream ! "
    "audioconvert ! audioresample ! "
    "audio/x-raw,rate=48000,channels=2 ! clocksync ! audio.sink"
)
```

**Key Features:**

**Timestamp Handling:**
- `do-timestamp=true` - rtmpsrc generates proper timestamps
- `clocksync` - Synchronizes audio/video to prevent drift
- Prevents "audio lagging" warnings in OBS logs

**Queue Management:**
- `max-size-buffers=3` (video) - Small buffer, stays responsive
- `max-size-buffers=200` (audio) - Larger for smooth audio
- `leaky=downstream` - **Drops old data instead of building up lag**

**Audio Normalization:**
- `audioresample` - Resamples to consistent rate
- `rate=48000,channels=2` - Forces 48kHz stereo (OBS standard)

**Video Normalization:**
- `videoscale` - Scales to target resolution
- `width=1920,height=1080` - Forces 1080p output
- Maintains aspect ratio with letterboxing

**Why This Helps:**
- ✅ Eliminates audio lag warnings
- ✅ Prevents timestamp drift (the root cause of choppy playback)
- ✅ Leaky queues prevent buffer buildup
- ✅ Synchronized clocks keep A/V in sync

### OBS Source Properties

The dynamically created sources are configured with optimal settings:

**Timestamp Settings:**
```python
"use_timestamps_video": True       # Use pipeline timestamps
"use_timestamps_audio": True       # Use pipeline timestamps  
"normalize_timestamps": False      # Let clocksync handle normalization
"reset_timestamps_on_discontinuity": False  # clocksync manages jumps
"max_timestamp_jump": 0            # Disabled - clocksync handles it
"sync_appsinks": True              # Sync to clock (works with clocksync)
```

**Buffer Settings:**
```python
"video_buffer_size": 0             # Use pipeline queue (max-size-buffers=3)
"audio_buffer_size": 0             # Use pipeline queue (max-size-buffers=200)
"buffering_enabled": False         # No extra buffering - clocksync manages it
```

**Reliability Settings:**
```python
"drop_on_latency": True            # Drop frames if sink too slow
"restart_on_eos": True             # Auto-restart on stream end
"restart_on_error": True           # Auto-restart on pipeline error
"restart_timeout": 2000            # Wait 2s before restart
```

These settings work together with the pipeline elements (`do-timestamp`, `clocksync`, `leaky=downstream`) to eliminate the "audio lagging" warnings and choppy playback.

### Readiness Polling

Default settings in `wait_for_source_ready()`:
- **Timeout**: 15 seconds
- **Poll Interval**: 0.5 seconds
- **Success Condition**: `mediaState == "OBS_MEDIA_STATE_PLAYING"`

### Source Naming

Sources are named with an incrementing counter:
- First source: `GMOTHERSTREAM_1`
- Second source: `GMOTHERSTREAM_2`
- And so on...

### Z-Order (Layer Position)

Dynamically created sources are automatically positioned **5 layers below the top** of the scene to prevent covering overlays, text, and other important elements.

**Example scene with 10 items:**
```
Index 9: [Top overlay/text] ← Top layer
Index 8: [Chat widget]
Index 7: [Timer display]
Index 6: [Logo]
Index 5: [Border/frame]
Index 4: [GMOTHERSTREAM_X] ← New stream source (5 from top)
Index 3: [Background effects]
Index 2: [Lower third]
Index 1: [Static background]
Index 0: [Base layer] ← Bottom layer
```

This ensures your overlays, alerts, and text elements always stay visible on top of the stream source.

**Adjusting Z-Offset:**

If 5 layers isn't the right position for your scene setup, you can adjust it:

```bash
# Set sources to appear 3 layers from top instead of 5
curl -X POST "http://localhost:8000/debug/set-source-z-offset?z_offset=3"

# Set sources to the top layer (0 = top, will cover everything)
curl -X POST "http://localhost:8000/debug/set-source-z-offset?z_offset=0"

# Check current setting
curl http://localhost:8000/debug/get-source-z-offset
```

**Examples:**
- `z_offset=0` - Source on top (covers all overlays) 
- `z_offset=3` - 3 layers of overlays on top
- `z_offset=5` - **Default** - 5 layers of overlays on top
- `z_offset=10` - Source near bottom (good if you have many overlay elements)

## Testing

### 1. Manual Testing via API

Test the dynamic source creation directly:

```bash
curl -X POST "http://localhost:8000/debug/test-dynamic-source-switch" \
  -H "Content-Type: application/json" \
  -d '{
    "rtmp_url": "rtmp://127.0.0.1:1935/motherstream/live",
    "scene_name": "MOTHERSTREAM"
  }'
```

### 2. Integration Testing

Use the existing E2E tests with monitoring:

```bash
# Run with the new approach
./tests/e2e/run-monitored-test.sh orderly

# Monitor logs for the new behavior
tail -f logs/motherstream.log | grep -E "GMOTHERSTREAM_|Creating new|Switching to new"
```

### 3. Monitoring Source Readiness

Watch for these log messages:

```
Creating new GStreamer source 'GMOTHERSTREAM_2' with URL: rtmp://...
Waiting for source 'GMOTHERSTREAM_2' to become ready (timeout: 15s)
Source 'GMOTHERSTREAM_2' state: OBS_MEDIA_STATE_BUFFERING
Source 'GMOTHERSTREAM_2' state: OBS_MEDIA_STATE_PLAYING
Source 'GMOTHERSTREAM_2' is PLAYING after 3.45s
Hiding old source 'GMOTHERSTREAM_1'
Showing new source 'GMOTHERSTREAM_2'
Successfully switched to new source 'GMOTHERSTREAM_2'
Cleaned up old source 'GMOTHERSTREAM_1'
```

### 4. Using OBS Monitoring Script

The existing monitoring script can track the new sources:

```bash
# Modify SOURCE_NAME in obs-stream-switch-monitor.py to track dynamic sources
# Or use it as-is to see when sources appear/disappear
python3 tests/e2e/obs-stream-switch-monitor.py --poll-interval 0.2
```

## Expected Behavior

### Successful Switch

1. **Creation**: New source created in ~0.1s
2. **Buffering**: Source enters BUFFERING state immediately
3. **Ready**: Source enters PLAYING state in 3-10s (depends on stream)
4. **Visibility**: Old source hidden, new source shown instantly
5. **Cleanup**: Old source removed after 1s grace period

### Failure Scenarios

#### New Source Never Becomes Ready

```
New source 'GMOTHERSTREAM_3' did not become ready within 15.0s
Failed to create new source
```

**Behavior**: New source is cleaned up, old source remains active

#### OBS Connection Lost

```
Failed to create GStreamer source 'GMOTHERSTREAM_3': WebSocket connection closed
```

**Behavior**: Automatic reconnection attempt, old source remains active

#### Source Creation Failed

```
Failed to create GStreamer source 'GMOTHERSTREAM_3': Input kind not found
```

**Possible Cause**: obs-gstreamer plugin not installed

## Troubleshooting

### Sources Keep Accumulating

**Problem**: Old sources not being cleaned up

**Check**:
```bash
curl http://localhost:8000/obs/list-inputs
```

**Solution**: Manually remove orphaned sources or restart OBS

### Source Never Becomes Ready

**Problem**: `wait_for_source_ready()` times out

**Possible Causes**:
1. Stream not actually publishing
2. RTMP URL incorrect
3. GStreamer pipeline incompatible with stream format
4. Network latency

**Debug**:
```bash
# Check if stream is publishing
curl http://localhost:8000/obs/media-input-status/GMOTHERSTREAM_X

# Check OBS logs for GStreamer errors
# On Linux: ~/.config/obs-studio/logs/
# On macOS: ~/Library/Application Support/obs-studio/logs/
```

**Fix Options**:

1. **If video stutters** - Increase video queue size in `obs.py`:
   ```python
   "d. ! queue max-size-buffers=5 leaky=downstream ! "  # Was 3, now 5
   ```

2. **If audio drops** - Increase audio queue size in `obs.py`:
   ```python
   "d. ! queue max-size-buffers=300 leaky=downstream ! "  # Was 200, now 300
   ```

3. **If clocksync causes issues** - Remove clocksync and adjust settings:
   ```python
   # Remove clocksync from both video and audio paths:
   "videoconvert ! video. "  # Removed clocksync
   "audio/x-raw,rate=48000,channels=2 ! audio."  # Removed clocksync
   
   # Then update settings:
   "sync_appsinks": False,  # Disable sync
   "buffering_enabled": True,  # Enable OBS buffering instead
   "reset_timestamps_on_discontinuity": True,  # Handle jumps manually
   "max_timestamp_jump": 10000,  # 10 second threshold
   ```

4. **If you need a different resolution** - Change width/height:
   ```python
   "videoscale ! video/x-raw,width=1280,height=720 ! "
   ```

5. **To disable scaling** - Remove videoscale:
   ```python
   "d. ! queue max-size-buffers=3 leaky=downstream ! videoconvert ! clocksync ! video. "
   ```

### Timestamp Issues Persist

**Problem**: Even with new sources, timestamps seem wrong

**Possible Causes**:
1. Issue is not in OBS but in upstream (SRS/Nginx)
2. GStreamer itself having timestamp handling issues
3. Stream encoding issues

**Next Steps**: Check SRS/Oryx configurations for timestamp handling

## Rollback Procedure

If the new approach causes issues, you can revert to the old behavior:

### 1. Revert `process_manager.py`

Change `start_stream()` back to:

```python
# Old approach
add_job(JobType.RESTART_MEDIA_SOURCE, payload={"source_name": "GMOTHERSTREAM"})
add_job(JobType.TOGGLE_OBS_SRC, payload={"source_name": "GMOTHERSTREAM", "only_off": False})
```

### 2. Manually Create Static Source

In OBS:
1. Add a GStreamer source named `GMOTHERSTREAM`
2. Set pipeline to: `rtmpsrc location=rtmp://HOST:PORT/motherstream/live ! ...`
3. Ensure it's in your scene

### 3. Restart the Application

```bash
docker-compose restart motherstream
```

## Performance Considerations

### Resource Usage

- **Brief Double Memory**: During switch, both sources exist for ~1-2 seconds
- **CPU Overhead**: GStreamer pipeline creation is CPU-intensive
- **OBS Load**: Creating/destroying sources puts load on OBS

### Optimization Opportunities

1. **Pre-create Next Source**: Create source when stream enters queue, not at switch time
2. **Source Pooling**: Reuse sources instead of creating/destroying
3. **Async Cleanup**: Delay old source cleanup to reduce switch time

## Known Limitations

1. **OBS Plugin Required**: Requires `obs-gstreamer` plugin installed
2. **Source Naming**: Counter increments indefinitely (wraps at ~4 billion)
3. **No Crossfade**: Sources switch instantly, no transition effect
4. **Buffering Delay**: Minimum 3-10s delay while new source buffers

## Future Improvements

- [ ] Add configurable timeout for source readiness
- [ ] Implement source pre-creation when stream queues
- [ ] Add crossfade transition between sources
- [ ] Track source creation metrics (time to ready, failure rate)
- [ ] Add source pooling to reduce creation overhead
- [ ] Auto-cleanup orphaned sources on startup

## Related Documentation

- **[Stream Health Monitoring](STREAM-HEALTH-MONITORING.md)** - 📊 Deep visibility into stream performance and playback issues
- [OBS Monitoring](tests/e2e/README-obs-monitoring.md) - Monitoring stream switches
- [OBS Stability](OBS_STABILITY_IMPROVEMENTS.md) - Connection health and job delays
- [GStreamer Pipeline](gstreamer-pipeline.md) - Pipeline configuration details
- [Testing Guide](DYNAMIC-SOURCE-TESTING-GUIDE.md) - Step-by-step testing procedures

## Diagnosing Playback Issues

If you experience stuttering, buffering, or other playback issues, use the **Stream Health Monitoring** system:

```bash
# Check real-time health
curl http://localhost:8000/stream-health/current

# View health history
curl http://localhost:8000/stream-health/history?count=50

# Get monitoring status and report location
curl http://localhost:8000/stream-health/status
```

See [STREAM-HEALTH-MONITORING.md](STREAM-HEALTH-MONITORING.md) for complete details.

## Questions?

Check logs for detailed execution flow:
```bash
tail -f logs/motherstream.log | grep -E "SWITCH_GSTREAMER_SOURCE|Creating new|Waiting for|Successfully switched"
```

