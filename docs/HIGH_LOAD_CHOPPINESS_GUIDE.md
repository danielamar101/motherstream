# High Load Choppiness Diagnostic Guide

## 🎯 The Problem

**You see**: Choppy video/audio when many streams are concurrent
**Health checks say**: Everything is fine ✅
**Why**: Your monitoring checks **INPUT** streams, not **OUTPUT** quality

## Understanding the Two Types of Monitoring

### 1. **Input Stream Monitoring** (What you have)
```
Incoming RTMP Streams → [Monitoring] → OBS
                         ↑
                    Checks these
```
**Monitors**: Individual stream quality (FPS, buffering, timestamps)
**Problem**: All inputs can be perfect while OUTPUT is choppy!

### 2. **Output Stream Monitoring** (What was missing)
```
OBS → [Encoding/Streaming] → YouTube/Viewers
                ↑
           Checks this
```
**Monitors**: OBS encoding performance, render lag, skipped frames
**This catches**: System overload, CPU bottlenecks, quality degradation

## 🔍 What Causes "Healthy Inputs, Choppy Output"

### Scenario: 50 Concurrent Streams

```
Input Health Checks:
  Stream 1: FPS 30.0 ✅ Healthy
  Stream 2: FPS 30.0 ✅ Healthy
  Stream 3: FPS 30.0 ✅ Healthy
  ...all 50 streams look perfect...

OBS Output (to viewers):
  Encoding Skip Rate: 8.5 fps ⚠️  CRITICAL
  Render FPS: 24.3 ⚠️  Below target
  Frame Time: 55ms ⚠️  Too slow
  
  → Result: CHOPPY OUTPUT!
```

**Why**: CPU is maxed out encoding 50 streams, so OBS starts:
- Skipping encoding frames (choppiness!)
- Dropping render FPS (stuttering!)
- Taking longer per frame (lag!)

## 🚨 Critical Metrics for High Load

### 1. **Encoding Skip Rate** (MOST IMPORTANT)
```
What it is: Frames per second being skipped by encoder
Why choppy: Skipped frames = missing video frames = stutter

Thresholds:
  0.0 fps:      ✅ Perfect
  0.1-1.0 fps:  ⚠️  Warning - approaching limit
  1.0-5.0 fps:  ❌ Degraded - visible choppiness
  > 5.0 fps:    🚨 Critical - very choppy
```

**Example:**
```
Time  Encoding Skip Rate   What viewers see
0s    0.0 fps             Smooth video
10s   0.5 fps             Occasional micro-stutter
20s   2.5 fps             Noticeable choppiness
30s   8.0 fps             Very choppy, unwatchable
```

### 2. **Render Skip Rate**
```
What it is: Frames per second being skipped in rendering
Why choppy: OBS can't render frames fast enough

Thresholds:
  0.0 fps:      ✅ Perfect
  > 1.0 fps:    ⚠️  Warning
  > 5.0 fps:    ❌ Critical
```

### 3. **Active FPS**
```
What it is: Actual output framerate
Target: 30.0 fps (or your stream FPS)

Thresholds:
  29-30 fps:    ✅ Perfect
  28-29 fps:    ⚠️  Warning
  25-28 fps:    ❌ Degraded
  < 25 fps:     🚨 Critical
```

### 4. **Frame Render Time**
```
What it is: Milliseconds to render each frame
Target: ~33ms (for 30 FPS)

Thresholds:
  < 35ms:       ✅ Perfect
  35-40ms:      ⚠️  Acceptable
  40-50ms:      ❌ Slow
  > 50ms:       🚨 Too slow (causes lag)
```

## 🛠️ Using the New Output Monitor

### Setup

The OBS output monitor has been added to your codebase. To use it:

```python
from app.core.obs_output_monitor import OBSOutputMonitor

# In your app initialization (where OBS is created):
output_monitor = OBSOutputMonitor(
    obs_manager=obs_socket_manager,
    poll_interval=2.0  # Check every 2 seconds
)

# Start monitoring
output_monitor.start_monitoring()

# Check current status
status = output_monitor.get_current_status()
if status and status['is_degraded']:
    print(f"⚠️  Output degraded: {status['issues']}")

# Stop monitoring (generates report)
output_monitor.stop_monitoring()
```

### API Endpoint (Add to your http_endpoints.py)

```python
@app.get("/obs-output/status")
async def get_obs_output_status():
    """Get current OBS output performance status"""
    status = output_monitor.get_current_status()
    if not status:
        return {"error": "Monitoring not active"}
    return status
```

### Check Status via API

```bash
# Check current output health
curl http://localhost:8000/obs-output/status

# Example response when healthy:
{
  "timestamp": "2025-11-14T10:30:45",
  "is_streaming": true,
  "active_fps": 30.0,
  "render_skip_rate": 0.0,
  "encoding_skip_rate": 0.0,
  "health_score": 100.0,
  "is_degraded": false,
  "issues": []
}

# Example response when degraded:
{
  "timestamp": "2025-11-14T10:35:22",
  "is_streaming": true,
  "active_fps": 26.3,
  "render_skip_rate": 1.2,
  "encoding_skip_rate": 5.8,
  "health_score": 45.0,
  "is_degraded": true,
  "issues": [
    "LOW_FPS_26.3",
    "CRITICAL_ENCODING_SKIPPING_5.8fps"
  ]
}
```

## 📊 Diagnostic Workflow

### Step 1: Run Load Test with Output Monitoring

```bash
# Terminal 1: Start OBS output monitoring
# (Add this to your app startup or trigger via API)

# Terminal 2: Run network monitor
cd /home/motherstream/Desktop/motherstream/scripts
./network_monitor.py --interval 5

# Terminal 3: Run load test
./stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 50
```

### Step 2: Monitor for Issues

Watch for these signs:

**In Terminal 1 (OBS Output Monitor):**
```
⚠️  OBS output degraded: ENCODING_SKIPPING_3.2fps
⚠️  OBS output degraded: LOW_FPS_27.5, ENCODING_SKIPPING_5.1fps
🚨 OBS output degraded: CRITICAL_ENCODING_SKIPPING_8.3fps
```

**In Terminal 2 (Network Monitor):**
```
💻 SYSTEM:
  CPU:     95.3%  ← High!
  
⚠️  BOTTLENECKS DETECTED:
  • HIGH CPU: 95.3%
```

### Step 3: Correlate Issues

```
Concurrent Streams | CPU % | Encoding Skip Rate | Viewer Experience
------------------+-------+-------------------+-------------------
10                | 45%   | 0.0 fps           | Perfect ✅
20                | 68%   | 0.0 fps           | Perfect ✅
30                | 82%   | 0.2 fps           | Smooth ✅
40                | 91%   | 1.8 fps           | Occasional stutter ⚠️
50                | 97%   | 5.5 fps           | Choppy ❌
60                | 99%   | 12.3 fps          | Very choppy 🚨
```

**Finding**: CPU bottleneck at ~40 streams, causing encoding lag

### Step 4: Find Your Capacity

The point where encoding starts skipping IS your capacity:

```
Encoding Skip Rate > 1.0 fps = Capacity reached
```

## 🔧 Solutions by Root Cause

### Cause 1: CPU Bottleneck (Most Common)

**Symptoms:**
- High CPU (>90%)
- High encoding skip rate
- Correlates with concurrent stream count

**Solutions:**

1. **Immediate: Reduce encoding load**
   ```python
   # In OBS settings, use faster encoder preset
   encoder_settings = {
       'preset': 'veryfast',  # Was 'fast' or 'medium'
       # or even 'superfast' or 'ultrafast' for more streams
   }
   ```

2. **Short-term: Use hardware encoding**
   ```python
   # NVENC (NVIDIA)
   encoder = 'jim_nvenc'
   
   # QuickSync (Intel)
   encoder = 'obs_qsv11'
   
   # VideoToolbox (macOS)
   encoder = 'com.apple.videotoolbox.videoencoder'
   ```

3. **Long-term: Scale horizontally**
   - Run multiple OBS instances
   - Distribute streams across servers
   - Use load balancer

### Cause 2: Network Bandwidth Saturation

**Symptoms:**
- High upload bandwidth (approaching line limit)
- Output bitrate drops
- Network errors/drops

**Solutions:**

1. **Reduce output bitrate**
   ```python
   bitrate = 2500  # Reduce from 3500
   ```

2. **Upgrade network connection**
   - 1 Gbps → 10 Gbps
   - Multiple NICs

3. **Adaptive bitrate**
   - Dynamically reduce quality under load

### Cause 3: Memory Pressure

**Symptoms:**
- Memory >90%
- Increasing memory over time
- System swapping

**Solutions:**

1. **Reduce buffer sizes**
   ```python
   max_size_buffers = 3  # Reduce from 5
   ```

2. **Add more RAM**

3. **Check for memory leaks**

### Cause 4: Scene Complexity

**Symptoms:**
- High render skip rate
- Long frame times (>40ms)
- Normal CPU/encoding stats

**Solutions:**

1. **Simplify scene**
   - Remove filters
   - Reduce transformations
   - Lower canvas resolution

2. **Upgrade GPU**

## 📈 Capacity Planning Matrix

Based on your test results, fill in this matrix:

```
Metric                    | 10 Streams | 20 Streams | 30 Streams | 40 Streams | 50 Streams
--------------------------+------------+------------+------------+------------+-----------
CPU %                     |            |            |            |            |
Encoding Skip Rate (fps)  |            |            |            |            |
Render Skip Rate (fps)    |            |            |            |            |
Active FPS                |            |            |            |            |
Upload Bandwidth (Mbps)   |            |            |            |            |
Viewer Experience         |            |            |            |            |
```

**Find the breaking point** where encoding skip rate > 1.0 fps

**Set production limit** to 80% of that number

## 🎯 Recommended Thresholds

Based on your testing, configure alerts:

```python
# Green: Everything fine
if encoding_skip_rate < 0.5 and cpu < 80 and fps > 29:
    status = "HEALTHY"
    
# Yellow: Approaching capacity
elif encoding_skip_rate < 1.5 or cpu > 80 or fps < 29:
    status = "WARNING"
    action = "Consider scaling soon"
    
# Red: Over capacity
elif encoding_skip_rate > 2.0 or cpu > 90 or fps < 27:
    status = "DEGRADED"
    action = "Reduce load immediately"
    
# Critical: Severe degradation
elif encoding_skip_rate > 5.0 or cpu > 95 or fps < 25:
    status = "CRITICAL"
    action = "Emergency: Reject new streams"
```

## 📝 Log Files

Output monitor creates:

```
docker-volume-mounts/logs/obs-output/
├── obs-output-20251114-103045.csv           # Detailed metrics
└── obs-output-report-20251114-110000.txt    # Summary report
```

**CSV columns:**
- timestamp
- active_fps
- render_skip_rate
- encoding_skip_rate
- current_bitrate_mbps
- health_score
- issues

**Report contains:**
- Performance summary
- Issue frequency
- Recommendations

## 🚀 Action Plan

1. ✅ Add OBS output monitor to your app
2. ✅ Run capacity test with both monitors
3. ✅ Find your breaking point (encoding skip rate > 1.0)
4. ✅ Set production limit to 80% of breaking point
5. ⬜ Configure alerts for encoding skip rate
6. ⬜ Implement graceful degradation
7. ⬜ Plan scaling strategy

## 💡 Key Takeaway

**The choppiness you're seeing is OBS struggling to encode/render under high load, NOT the input streams having quality issues.**

Monitor OBS output performance, not just input stream health!

---

**With this new monitoring, you'll see:**

```
Input Health: ✅ All streams perfect
Output Health: ❌ Encoding skipping 5.8 fps

→ NOW YOU KNOW THE REAL PROBLEM! 🎯
```

