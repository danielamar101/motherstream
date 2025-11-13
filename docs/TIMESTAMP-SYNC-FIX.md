# Timestamp Sync Fix - Audio Lag Elimination

## Problem Identified

OBS logs showed severe audio timestamp lag issues:
```
warning: Source GMOTHERSTREAM_1 audio is lagging (over by 7467.53 ms)
warning: Source GMOTHERSTREAM_2 audio is lagging (over by 2111.93 ms)
warning: Source GMOTHERSTREAM_3 audio is lagging (over by 7216.96 ms)
```

This caused:
- 🎞️ Choppy/stuttering video playback
- 🔊 Audio constantly restarting
- ⏱️ Timestamps drifting up to 7+ seconds
- 🔄 Poor viewer experience

## Root Cause

The previous GStreamer pipeline didn't properly handle timestamps:
- No timestamp generation at source
- No synchronization between audio/video  
- Queues accumulated lag instead of dropping old data
- No audio resampling for format consistency

## Solution Implemented

### 1. Updated GStreamer Pipeline

**Old Pipeline (Problematic):**
```python
f"rtmpsrc location={rtmp_url} ! "
"decodebin name=d "
"d. ! queue ! videoscale ! video/x-raw,width=1920,height=1080 ! videoconvert ! video.sink "
"d. ! queue ! audioconvert ! audio.sink"
```

**New Pipeline (Timestamp-Aware):**
```python
f"rtmpsrc location={rtmp_url} do-timestamp=true ! "
"decodebin name=d "
# Video: small buffer, drops old data, scales, syncs
"d. ! queue max-size-buffers=3 leaky=downstream ! "
"videoscale ! video/x-raw,width=1920,height=1080 ! "
"videoconvert ! clocksync ! video. "
# Audio: larger buffer, resamples, syncs
"d. ! queue max-size-buffers=200 leaky=downstream ! "
"audioconvert ! audioresample ! "
"audio/x-raw,rate=48000,channels=2 ! clocksync ! audio."
```

### 2. Key Pipeline Changes

| Element | Purpose | Benefit |
|---------|---------|---------|
| `do-timestamp=true` | rtmpsrc generates timestamps | Proper timing from source |
| `max-size-buffers=3` (video) | Small buffer | Low latency, responsive |
| `max-size-buffers=200` (audio) | Larger buffer | Smooth audio |
| `leaky=downstream` | Drop old data | **Prevents lag buildup!** |
| `clocksync` | Sync to pipeline clock | A/V sync, no drift |
| `audioresample` | Resample audio | Consistent format |
| `rate=48000,channels=2` | Force 48kHz stereo | OBS standard |
| `video.` / `audio.` | obs-gstreamer sinks | macOS compatibility |

### 3. OBS Source Properties

Set optimal properties for timestamp handling:

```python
inputSettings={
    "pipeline": gstreamer_pipeline,
    
    # Timestamp Settings (Let clocksync manage)
    "use_timestamps_video": True,
    "use_timestamps_audio": True,
    "normalize_timestamps": False,          # clocksync handles it
    "reset_timestamps_on_discontinuity": False,  # clocksync handles it
    "max_timestamp_jump": 0,                # Disabled
    "sync_appsinks": True,                  # Work with clocksync
    
    # Buffer Settings (Pipeline queues handle it)
    "video_buffer_size": 0,                 # Use queue max-size-buffers=3
    "audio_buffer_size": 0,                 # Use queue max-size-buffers=200
    "buffering_enabled": False,             # No extra buffering
    
    # Reliability
    "drop_on_latency": True,                # Drop if too slow
    "restart_on_eos": True,                 # Auto-restart
    "restart_on_error": True,               # Auto-restart
    "restart_timeout": 2000,                # 2s wait
}
```

## Expected Results

After deploying these changes:

### ✅ Immediate Benefits
- **No more "audio lagging" warnings** in OBS logs
- **Smooth, continuous playback** without stuttering
- **Proper A/V synchronization** maintained
- **Consistent audio format** (48kHz stereo)

### ✅ Long-Term Benefits
- Timestamps stay synchronized over long streaming sessions
- Leaky queues prevent buffer buildup
- Auto-restart handles connection issues gracefully
- Works consistently across Linux and macOS

## Verification

### 1. Check OBS Logs (Primary Indicator)

**Before Fix:**
```
warning: Source GMOTHERSTREAM_X audio is lagging (over by XXXX ms)
# Repeating constantly
```

**After Fix:**
```
# Should be quiet! No lag warnings.
```

**How to Monitor:**
```bash
# Linux
tail -f ~/.config/obs-studio/logs/*.txt | grep -i "lagging\|audio"

# macOS  
tail -f ~/Library/Application\ Support/obs-studio/logs/*.txt | grep -i "lagging\|audio"
```

### 2. Stream Health Monitoring

```bash
# Check frame drop rate (should be low/null)
curl https://motherstream.live/backend/stream-health/current | jq '.health.frame_drop_rate'

# Check overall health (should be 90-100)
curl https://motherstream.live/backend/stream-health/current | jq '.health.health_score'

# Check for pipeline warnings
curl https://motherstream.live/backend/stream-health/current | jq '.health.pipeline_warnings'
```

### 3. Visual/Audio Check

- ✅ Video plays smoothly without stuttering
- ✅ Audio doesn't cut out or restart
- ✅ Lip sync maintained (A/V synchronized)
- ✅ No frozen frames during stream switches

## Troubleshooting

### If Video Still Stutters

**Increase video queue:**
```python
"d. ! queue max-size-buffers=5 leaky=downstream ! "  # Was 3
```

### If Audio Still Drops

**Increase audio queue:**
```python
"d. ! queue max-size-buffers=300 leaky=downstream ! "  # Was 200
```

### If clocksync Causes Problems

**Remove clocksync and use OBS buffering:**
```python
# Pipeline without clocksync:
"videoconvert ! video. "
"audio/x-raw,rate=48000,channels=2 ! audio."

# Update settings:
"sync_appsinks": False,
"buffering_enabled": True,
"reset_timestamps_on_discontinuity": True,
"max_timestamp_jump": 10000,
```

### If Latency Too High

**Reduce buffer sizes:**
```python
"d. ! queue max-size-buffers=2 leaky=downstream ! "  # Video
"d. ! queue max-size-buffers=100 leaky=downstream ! "  # Audio
```

## Technical Details

### Why `leaky=downstream` is Critical

Without `leaky=downstream`, queues accumulate data when:
- Network hiccups occur
- Stream bitrate fluctuates  
- Downstream processing slows

This causes **timestamp lag** to build up over time (7+ seconds!).

With `leaky=downstream`, the queue:
- ✅ Drops **old data** when full
- ✅ Always outputs **recent data**
- ✅ Maintains **low latency**
- ✅ Prevents **lag accumulation**

### Why `clocksync` is Important

`clocksync` element:
- Synchronizes timestamps to pipeline clock
- Prevents drift between audio and video
- Handles timestamp discontinuities gracefully
- Works with `do-timestamp=true` for consistent timing

### Why Different Queue Sizes

**Video (3 buffers):**
- Smaller = more responsive
- Less latency
- Can afford occasional drops (humans less sensitive)

**Audio (200 buffers):**
- Larger = smoother playback
- Prevents audio clicks/pops
- Humans very sensitive to audio glitches

## Files Modified

1. **`app/obs.py`** - Updated pipeline and source properties
2. **`DYNAMIC-SOURCE-SWITCHING.md`** - Updated documentation
3. **`gstreamer-pipeline.md`** - Added production pipeline examples
4. **`TIMESTAMP-SYNC-FIX.md`** - This document

## Deployment

After merging these changes:

1. **Stop current streams** (or let them finish naturally)
2. **Deploy updated code**
3. **Next stream switch** will use new pipeline
4. **Monitor OBS logs** for absence of lag warnings
5. **Check stream health API** for confirmation

## Success Criteria

✅ **Primary**: No "audio lagging" warnings in OBS logs  
✅ **Secondary**: Health score consistently > 90  
✅ **Tertiary**: Smooth visual playback confirmed by viewers  
✅ **Quaternary**: Frame drop rate < 1.0 fps  

## Related Documentation

- [Dynamic Source Switching](DYNAMIC-SOURCE-SWITCHING.md) - Main system docs
- [Stream Health Monitoring](STREAM-HEALTH-MONITORING.md) - Health metrics
- [GStreamer Pipeline](gstreamer-pipeline.md) - Pipeline configurations

## Questions?

If issues persist after deployment:
1. Check OBS logs for specific error messages
2. Review stream health metrics API
3. Try troubleshooting steps above
4. Consider temporarily removing `clocksync` as fallback

