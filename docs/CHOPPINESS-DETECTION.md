# Enhanced Choppiness Detection

## Why Monitoring Didn't Detect Your Choppiness

### What Was Being Checked (Before)

The original monitoring only looked at:
- ✅ **OBS FPS** - Average framerate (e.g., 30 FPS)
- ✅ **Dropped Frames** - Cumulative count
- ✅ **Media State** - PLAYING, BUFFERING, STOPPED
- ✅ **Visibility** - Is source shown?

### The Problem

**Your stream can appear "healthy" by these metrics while still being choppy!**

Here's why:

**Scenario: Choppy Playback with "Perfect" Stats**
```
OBS FPS: 30.0          ← Looks perfect!
Media State: PLAYING    ← Looks perfect!
Dropped Frames: 173     ← Seems stable (not increasing rapidly)
Health Score: 100       ← Says everything is fine!

BUT: Video is visibly stuttering and choppy!
```

## What Causes "Invisible" Choppiness

### 1. **FPS Variance** (Not Just Average)
```
Time  FPS
0s    30.0  ← Average looks fine
1s    28.0
2s    32.0
3s    26.0  ← Dips cause stutter
4s    31.0
5s    33.0

Average: 30.0 FPS  ✓ "Healthy"
Variance: 7 FPS    ✗ Actually choppy!
```

**What you see**: Micro-stutters every few seconds even though "FPS is 30"

### 2. **Playback Stalls** (Timestamp Not Progressing)
```
Time    Media Time (should increase)
0s      1234ms
1s      1234ms  ← Stalled! Not progressing
2s      1234ms  ← Still stalled!
3s      3456ms  ← Jumped forward

State: PLAYING ✓ "Healthy"
Reality: Frozen for 2 seconds!
```

**What you see**: Frame freezes for a moment, then jumps forward

### 3. **Timestamp Jumps** (Even Small Ones)
```
Time    Expected Delta    Actual Delta    
0s      1000ms           1000ms  ✓
1s      1000ms           1350ms  ← Jump! Choppy
2s      1000ms           850ms   ← Jump back!
3s      1000ms           1000ms  ✓

State: PLAYING, FPS: 30 ✓ "Healthy"
Reality: Visible stuttering!
```

**What you see**: Jerky playback, skipped/repeated frames

### 4. **Intermittent FPS Drops**
```
Most of the time: 30 FPS  ← Average calculation says "fine"
But occasionally: 18 FPS  ← These moments are VERY visible

Average over 10s: 29.5 FPS ✓ "Healthy"
Reality: Noticeable stutter every few seconds
```

**What you see**: Periodic stutters, not smooth

## Enhanced Detection Added

### New Checks

```python
# 1. FPS Variance Detection
if len(fps_history) >= 5:
    fps_variance = max(fps_history) - min(fps_history)
    if fps_variance > 5:
        # DETECTED: FPS is jumping around too much
        issues.append("CHOPPY_FPS_VARIANCE")
        score -= 20

# 2. Playback Stall Detection  
if media_time not progressing for 3+ polls:
    # DETECTED: Playback frozen
    issues.append("CHOPPY_STALLED")
    score -= 30

# 3. Timestamp Jump Detection
time_delta = current_time - previous_time
expected = poll_interval * 1000
if abs(time_delta - expected) > 200ms:
    # DETECTED: Timestamp jump
    issues.append("CHOPPY_TIMESTAMP_JUMP")
    score -= 25

# 4. FPS Drop Detection (not just average)
if any recent FPS < 24:
    # DETECTED: Recent FPS drop
    issues.append("CHOPPY_FPS_DROPS")
    score -= 15
```

### New Issue Types You'll See

When choppiness is detected, you'll now see these in the issues list:

- **`CHOPPY_FPS_VARIANCE`** - FPS jumping around (e.g., 30→25→32→28)
- **`CHOPPY_FPS_DROPS`** - Occasional drops below 24 FPS
- **`CHOPPY_STALLED`** - Playback freezing (media time not progressing)
- **`CHOPPY_TIMESTAMP_JUMP`** - Timestamp discontinuities causing jerky playback

### New Pipeline Warnings

The `pipeline_warnings` field will show:
- `FPS_VARIANCE_X.X` - Shows actual variance value
- `FPS_DROPS_DETECTED` - Drops happened recently
- `PLAYBACK_STALLED` - Detected freeze
- `TIMESTAMP_JUMP_Xms` - Shows jump size

## Using Enhanced Detection

### Check for Choppiness in Real-Time

```bash
# Watch for choppiness indicators
curl -s https://motherstream.live/backend/stream-health/current | jq '{
  health_score: .health.health_score,
  issues: .health.issues,
  pipeline_warnings: .health.pipeline_warnings,
  fps: .health.obs_fps
}'
```

**Example Output (Choppy Stream):**
```json
{
  "health_score": 65.0,
  "issues": ["CHOPPY_FPS_VARIANCE", "CHOPPY_FPS_DROPS"],
  "pipeline_warnings": [
    "FPS_VARIANCE_7.2",
    "FPS_DROPS_DETECTED"
  ],
  "fps": 30.0
}
```

**Before enhancement**, this would have shown:
```json
{
  "health_score": 100.0,  ← False positive!
  "issues": [],
  "fps": 30.0
}
```

### Monitor Over Time

```bash
# Watch for patterns
watch -n 1 'curl -s https://motherstream.live/backend/stream-health/current | jq ".health.pipeline_warnings"'
```

**Healthy Stream:**
```json
[]  # No warnings
```

**Choppy Stream:**
```json
["FPS_VARIANCE_6.5", "FPS_DROPS_DETECTED"]
["TIMESTAMP_JUMP_350ms"]
["FPS_VARIANCE_8.1", "PLAYBACK_STALLED"]
```

## What Each Detection Means

### FPS Variance

**What it detects:** Inconsistent framerate over last 5 samples

**Threshold:** Variance > 5 FPS

**Example:**
```
FPS samples: [30.0, 28.5, 32.0, 26.5, 31.0]
Variance: 32.0 - 26.5 = 5.5 FPS
Result: CHOPPY_FPS_VARIANCE detected
```

**Causes:**
- System CPU load fluctuating
- Network jitter causing decode delays
- GStreamer pipeline struggling with variable bitrate
- Competing processes on system

**Fix:**
- Reduce system load
- Increase CPU priority for OBS
- Ask streamers to use CBR (constant bitrate)
- Check network stability

### FPS Drops

**What it detects:** Any of last 3 FPS samples below 24

**Threshold:** FPS < 24

**Example:**
```
FPS samples: [30.0, 30.0, 22.5, 30.0, 29.5]
                    ↑ This drop is detected!
Result: CHOPPY_FPS_DROPS detected
```

**Causes:**
- Brief CPU spikes
- Other applications stealing resources
- GStreamer decode lag
- System context switches

**Fix:**
- Close unnecessary applications
- Reduce OBS encoding load
- Use hardware decoding if available
- Increase process priority

### Playback Stalls

**What it detects:** Media time not advancing for 3+ polls

**Example:**
```
Poll 1: media_time = 5000ms
Poll 2: media_time = 5000ms  ← Not advancing!
Poll 3: media_time = 5000ms  ← Still not advancing!
Result: CHOPPY_STALLED detected
```

**Causes:**
- **Source stream paused/froze** ← Most common!
- Network completely stalled
- GStreamer pipeline deadlocked
- Severe CPU starvation

**Fix:**
- Check incoming stream quality at source
- Monitor network connection
- Restart GStreamer pipeline if persistent
- Check for system-wide freeze (unlikely)

### Timestamp Jumps

**What it detects:** Time delta differs from expected by >200ms

**Threshold:** |actual_delta - expected_delta| > 200ms

**Example:**
```
Poll interval: 1000ms
Expected delta: 1000ms

Poll 1: media_time = 1000ms
Poll 2: media_time = 2350ms  ← Jump of 1350ms!
Expected: 2000ms
Delta: 1350ms vs 1000ms = 350ms jump
Result: CHOPPY_TIMESTAMP_JUMP detected
```

**Causes:**
- **Timestamp issues in source stream** ← Common with bad encoders!
- Network packet reordering
- GStreamer clock drift
- RTMP timestamp discontinuities

**Fix:**
- This is exactly what our pipeline fixes are for!
- Verify `do-timestamp=true` is working
- Check `clocksync` elements are in pipeline
- May need to increase `leaky` queue aggressiveness

## Interpreting Combined Indicators

### Pattern 1: Frequent FPS Variance + Drops
```
Issues: [CHOPPY_FPS_VARIANCE, CHOPPY_FPS_DROPS]
Warnings: [FPS_VARIANCE_8.2, FPS_DROPS_DETECTED]
```

**Diagnosis**: System struggling to maintain consistent performance

**Most Likely**: CPU/GPU overload or competing processes

**Fix**: Reduce system load, increase OBS priority

### Pattern 2: Timestamp Jumps + Stalls
```
Issues: [CHOPPY_TIMESTAMP_JUMP, CHOPPY_STALLED]
Warnings: [TIMESTAMP_JUMP_450ms, PLAYBACK_STALLED]
```

**Diagnosis**: Source stream has timestamp problems

**Most Likely**: Bad encoder at source, or network issues

**Fix**: Check source stream quality, verify pipeline settings

### Pattern 3: Consistent Stalls
```
Issues: [CHOPPY_STALLED]
Warnings: [PLAYBACK_STALLED, PLAYBACK_STALLED, PLAYBACK_STALLED]
```

**Diagnosis**: Playback repeatedly freezing

**Most Likely**: Source stream is actually freezing/pausing

**Fix**: Check streamer's encoder, network, or PC

### Pattern 4: Just FPS Variance (No Drops)
```
Issues: [CHOPPY_FPS_VARIANCE]
Warnings: [FPS_VARIANCE_6.5]
```

**Diagnosis**: FPS fluctuating but staying above 24

**Most Likely**: Minor system load variation

**Fix**: May be acceptable, or reduce background tasks

## Why This Matters

### Before Enhancement

```
Stream is choppy → Viewer complains → You check monitoring
Monitoring says: Health: 100, FPS: 30, State: PLAYING
You think: "Monitoring says it's fine, must be viewer's problem"
Reality: Stream IS choppy, monitoring just can't see it
```

### After Enhancement

```
Stream is choppy → Viewer complains → You check monitoring
Monitoring says: Health: 65, Issues: [CHOPPY_FPS_VARIANCE, CHOPPY_TIMESTAMP_JUMP]
You think: "Aha! FPS varying 7 FPS and timestamps jumping 350ms"
Reality: You can now see and fix the actual problem!
```

## Testing the Detection

### Simulate Choppiness

You can verify detection works by artificially degrading playback:

**1. CPU Load Test:**
```bash
# Stress CPU to cause FPS variance
stress --cpu 4 --timeout 60s
# Watch for CHOPPY_FPS_VARIANCE
```

**2. Network Jitter Test:**
```bash
# Add network delay variation
tc qdisc add dev eth0 root netem delay 100ms 50ms
# Watch for CHOPPY_TIMESTAMP_JUMP
```

**3. Compare Before/After:**
```bash
# Before enhancement: Would show health: 100
# After enhancement: Should detect issues
```

## Next Steps

1. **Deploy these changes**
2. **Monitor for 24 hours** with real streams
3. **Check which choppiness types appear most**
4. **Focus fixes on the specific issues detected**

The monitoring will now tell you **why** it's choppy, not just **if** it's choppy!

## Related Files

- `app/core/stream_metrics.py` - Implementation
- `STREAM-HEALTH-MONITORING.md` - General monitoring docs
- `TIMESTAMP-SYNC-FIX.md` - Pipeline fixes for timestamp issues

