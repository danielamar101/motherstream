# Stream Health Monitoring System

## Overview

The Stream Health Monitoring system provides deep visibility into GStreamer source performance to diagnose playback issues like stuttering, buffering, and frame drops.

## Problem It Solves

When watching stream playback, you might notice:
- 🎞️ Stuttering or choppy video
- ⏸️ Buffering pauses
- 📉 Frame drops
- 🔄 State transition issues

This system **automatically collects detailed metrics every second** to help you identify the root cause.

## What Gets Monitored

### OBS Media State
- `PLAYING` - Source is actively playing ✅
- `BUFFERING` - Source is loading data ⏳
- `STOPPED` - Source has stopped ⛔
- `PAUSED` - Source is paused ⏸️
- `ERROR` - Source encountered an error ❌

### Performance Metrics
- **OBS FPS** - Actual rendering framerate
- **Dropped Frames** - Frames skipped due to performance issues
- **Media Time/Duration** - Playback position
- **Visibility Status** - Whether source is shown

### Health Scoring
- **100** - Perfect, no issues
- **70-99** - Minor issues, acceptable
- **40-69** - Degraded performance
- **0-39** - Severe issues

### Issue Detection
Automatically flags:
- `BUFFERING` - Source is buffering
- `LOW_FPS_XX.X` - FPS below 20
- `REDUCED_FPS_XX.X` - FPS below 25
- `VISIBLE_NOT_PLAYING` - Source visible but not playing (frozen frame!)
- `SOURCE_STOPPED` - Source stopped unexpectedly
- `ERROR_STATE` - Source in error state

## How It Works

### Automatic Monitoring

**Monitoring starts automatically** when you create a new GStreamer source:

```python
# When this happens:
add_job(JobType.SWITCH_GSTREAMER_SOURCE, payload={
    "rtmp_url": "rtmp://...",
    "scene_name": "MOTHERSTREAM"
})

# The system automatically:
# 1. Creates the source
# 2. Starts health monitoring
# 3. Collects metrics every second
# 4. Logs to CSV file
# 5. Generates report when stopped
```

### Data Collection

Every second (configurable), the system collects:
1. OBS media input status
2. Source visibility
3. OBS rendering stats
4. Calculates health score
5. Detects issues
6. Logs to CSV
7. Keeps last 500 snapshots in memory

### 🆕 Hourly Aggregation System

**Why hourly files?**
- **Consolidation**: All streams in one place for easier analysis
- **Efficiency**: Fewer files to manage (24 per day vs. hundreds)
- **Comparison**: Easy to compare multiple streams side-by-side
- **Automation**: Reports generated automatically every hour
- **No empty files**: Files are only created when streams are actually active

**How it works:**
1. All stream monitors write to the **same hourly CSV file**
2. File naming: `stream-health-YYYYMMDD-HH0000.csv` (hour-based)
3. **Lazy creation**: Files are only created when there's actual stream data (no empty files!)
4. At the top of each hour:
   - Current file is closed
   - Report is automatically generated for that hour
   - New file is created only when streams become active
5. Thread-safe: Multiple streams can write simultaneously

### File Output

**🆕 HOURLY CSV FILES** - All streams are now aggregated into hour-long files:

**CSV File**: `logs/stream-metrics/stream-health-YYYYMMDD-HH0000.csv`
- **One file per hour** containing ALL streams
- Automatically rotates at the top of each hour
- Example: `stream-health-20251113-030000.csv` (3:00 AM - 3:59 AM)

```csv
timestamp,timestamp_str,source_name,rtmp_url,media_state,media_duration,media_time,is_visible,scene_name,obs_fps,dropped_frames,buffer_level,health_score,issues,poll_count
1699876543.123,2023-11-13 03:15:43.123,GMOTHERSTREAM_1,rtmp://...,OBS_MEDIA_STATE_PLAYING,0,1234,True,MOTHERSTREAM,30.0,0,,100.0,,1
1699876544.456,2023-11-13 03:15:44.456,GMOTHERSTREAM_2,rtmp://...,OBS_MEDIA_STATE_PLAYING,0,5678,True,MOTHERSTREAM,30.0,0,,100.0,,1
1699876545.789,2023-11-13 03:15:45.789,GMOTHERSTREAM_1,rtmp://...,OBS_MEDIA_STATE_PLAYING,0,2234,True,MOTHERSTREAM,30.0,0,,100.0,,2
```

**🆕 HOURLY REPORT FILES** - Generated automatically each hour:

**Report File**: `logs/stream-metrics/stream-health-YYYYMMDD-HH0000-report.txt`
- Health summary for **ALL streams** in that hour
- Per-stream breakdown with individual stats
- Aggregate issue frequency analysis
- Media state distribution across all streams
- Actionable recommendations

Example report structure:
```
======================================================================
HOURLY STREAM HEALTH MONITORING REPORT
======================================================================

Time Period: 20251113-03
Total Streams: 4
Total Data Points: 3600

OVERALL HEALTH SUMMARY:
  Average Health Score: 94.5/100
  Min Health Score: 50.0/100
  Max Health Score: 100.0/100

PER-STREAM BREAKDOWN:
  GMOTHERSTREAM_1:
    Data Points: 900
    Avg Health: 98.2/100
    Issues: None ✓
    
  GMOTHERSTREAM_2:
    Data Points: 900
    Avg Health: 92.1/100
    Issues: CHOPPY_STALLED, BUFFERING
...
```

## Usage

### 1. Check Current Health (Real-Time)

```bash
# Get the latest health snapshot
curl http://localhost:8000/stream-health/current
```

**Response:**
```json
{
  "status": "success",
  "health": {
    "timestamp": 1699876543.123,
    "source_name": "GMOTHERSTREAM_2",
    "media_state": "OBS_MEDIA_STATE_PLAYING",
    "is_visible": true,
    "obs_fps": 29.97,
    "health_score": 100.0,
    "issues": []
  },
  "monitoring_active": true
}
```

### 2. View Health History

```bash
# Get last 20 snapshots
curl http://localhost:8000/stream-health/history?count=20
```

This returns a time-series of health snapshots to spot patterns.

### 3. Check Monitoring Status

```bash
curl http://localhost:8000/stream-health/status
```

**Response:**
```json
{
  "status": "success",
  "monitoring_active": true,
  "current_source": "GMOTHERSTREAM_2",
  "rtmp_url": "rtmp://127.0.0.1:1935/motherstream/live",
  "poll_count": 127,
  "poll_interval": 1.0,
  "current_hourly_csv_file": "logs/stream-metrics/stream-health-20251113-030000.csv",
  "current_hour": "20251113-03",
  "history_size": 500,
  "note": "Now using hourly CSV files aggregating all streams"
}
```

### 4. Configure Monitoring

```bash
# Collect metrics more frequently (0.5 second interval)
curl -X POST "http://localhost:8000/stream-health/configure?poll_interval=0.5"

# Collect less frequently (2 second interval, lighter load)
curl -X POST "http://localhost:8000/stream-health/configure?poll_interval=2.0"
```

### 5. Manual Stop Monitoring

```bash
# Stop monitoring current source
curl -X POST http://localhost:8000/stream-health/stop
```

**Response:**
```json
{
  "status": "success",
  "message": "Stopped monitoring for 'GMOTHERSTREAM_2'",
  "csv_file": "logs/stream-metrics/stream-health-20251113-030000.csv",
  "note": "Using hourly CSV files - reports generated automatically each hour"
}
```

### 6. Manual Report Generation

**🆕 Generate reports for existing CSV files:**

```python
from app.core.stream_metrics import StreamHealthMonitor

# Generate or regenerate report for any hourly CSV file
StreamHealthMonitor.generate_report_for_csv(
    "/app/logs/stream-metrics/stream-health-20251113-030000.csv"
)
# Creates: stream-health-20251113-030000-report.txt
```

This is useful for:
- Regenerating reports after adjusting metrics
- Creating reports for archived CSV files
- Analysis of historical data

## Real-Time Monitoring Dashboard

### Terminal Monitor (Watch Live)

```bash
# Watch current health in real-time
watch -n 1 'curl -s http://localhost:8000/stream-health/current | jq ".health | {state: .media_state, fps: .obs_fps, score: .health_score, issues: .issues}"'
```

Output updates every second:
```json
{
  "state": "OBS_MEDIA_STATE_PLAYING",
  "fps": 29.97,
  "score": 100,
  "issues": []
}
```

### Log Tail

```bash
# Watch health warnings in application logs
tail -f logs/motherstream.log | grep "Stream health"
```

## Analyzing Results

### Example: Healthy Stream

```
Average Health Score: 98.5/100
Min Health Score: 95.0/100
Max Health Score: 100.0/100

ISSUES DETECTED:
  No issues detected! ✓

MEDIA STATE DISTRIBUTION:
  OBS_MEDIA_STATE_PLAYING: 120 polls (100.0%)

RECOMMENDATIONS:
  ✓ Stream health is excellent! No action needed.
```

**Diagnosis**: Everything working perfectly!

### Example: Buffering Issues

```
Average Health Score: 65.3/100
Min Health Score: 40.0/100
Max Health Score: 100.0/100

ISSUES DETECTED:
  BUFFERING: 45 times (37.5% of polls)
  VISIBLE_NOT_PLAYING: 12 times (10.0% of polls)

MEDIA STATE DISTRIBUTION:
  OBS_MEDIA_STATE_PLAYING: 67 polls (55.8%)
  OBS_MEDIA_STATE_BUFFERING: 45 polls (37.5%)
  OBS_MEDIA_STATE_STOPPED: 8 polls (6.7%)

RECOMMENDATIONS:
  ⚠ Stream health is acceptable but could be improved.
  → High buffering detected - check network bandwidth
  → Consider reducing stream bitrate
  → Source visible before ready - increase buffer time
```

**Diagnosis**: Network or bitrate issues causing frequent buffering

### Example: Low FPS

```
Average Health Score: 52.1/100

ISSUES DETECTED:
  LOW_FPS_18.5: 89 times (74.2% of polls)
  REDUCED_FPS_22.3: 18 times (15.0% of polls)

RECOMMENDATIONS:
  ✗ Stream health is poor. Immediate action recommended!
  → Low FPS detected - check system resources
  → Reduce OBS encoding load
```

**Diagnosis**: System performance issues (CPU, GPU, or encoding overload)

## Common Issues & Solutions

### Issue: Source Keeps Buffering

**Symptoms:**
- `BUFFERING` appears frequently in issues
- Health score drops to 60-80 range
- Video stutters periodically

**Possible Causes:**
1. Network bandwidth insufficient
2. Stream bitrate too high
3. Network latency/jitter
4. Upstream encoder issues

**Solutions:**
```bash
# Check network to RTMP server
ping -c 10 <rtmp-host>

# Monitor bandwidth usage
iftop

# Ask streamer to reduce bitrate
# Or increase network capacity
```

### Issue: Low FPS

**Symptoms:**
- `LOW_FPS_XX.X` or `REDUCED_FPS_XX.X` in issues
- OBS FPS consistently below 25-30
- Health score 40-70

**Possible Causes:**
1. OBS overloaded (encoding + rendering)
2. CPU/GPU at capacity
3. Too many sources in scene
4. Hardware limitations

**Solutions:**
```bash
# Check system resources
top
nvidia-smi  # If using GPU encoding

# Reduce OBS load:
# - Lower output resolution
# - Reduce encoding preset (faster = less load)
# - Remove unnecessary sources
# - Disable unused filters
```

### Issue: Visible Before Playing

**Symptoms:**
- `VISIBLE_NOT_PLAYING` appears
- Frozen frames at stream start
- Health score drops briefly

**Possible Cause:**
- Source made visible before buffered and ready

**Solution:**
This should be automatically handled by the dynamic source creation waiting for `PLAYING` state. If you see this, there may be a timing issue. Check the wait timeout in `wait_for_source_ready()`.

### Issue: Inconsistent Health Scores

**Symptoms:**
- Score varies wildly (100 → 40 → 100)
- Multiple different issues intermittently
- Unpredictable behavior

**Possible Causes:**
1. Intermittent network issues
2. Streamer connection unstable
3. System resource contention
4. Multiple apps competing for bandwidth

**Solutions:**
- Run monitoring for longer period (10+ minutes)
- Check for patterns (time of day, specific streamers)
- Monitor during known good/bad periods
- Compare multiple sessions

## Advanced Usage

### Long-Term Monitoring

Monitor a stream for an extended period:

```bash
# Start a stream switch (monitoring starts automatically)
# Let it run for 30 minutes while you watch

# Then check the results
curl http://localhost:8000/stream-health/status

# View the CSV for detailed analysis
cat logs/stream-metrics/stream-health-*.csv
```

### Comparative Analysis

Compare two different streams or configurations:

```python
import pandas as pd

# Load two monitoring sessions
stream1 = pd.read_csv('logs/stream-metrics/stream-health-GMOTHERSTREAM_1-20231113-101543.csv')
stream2 = pd.read_csv('logs/stream-metrics/stream-health-GMOTHERSTREAM_2-20231113-103022.csv')

# Compare average health
print(f"Stream 1 avg health: {stream1['health_score'].mean():.1f}")
print(f"Stream 2 avg health: {stream2['health_score'].mean():.1f}")

# Compare buffering frequency
buffering1 = stream1['issues'].str.contains('BUFFERING', na=False).sum()
buffering2 = stream2['issues'].str.contains('BUFFERING', na=False).sum()

print(f"Stream 1 buffering: {buffering1}/{len(stream1)} polls ({buffering1/len(stream1)*100:.1f}%)")
print(f"Stream 2 buffering: {buffering2}/{len(stream2)} polls ({buffering2/len(stream2)*100:.1f}%)")
```

### Graphing Health Over Time

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load data
df = pd.read_csv('logs/stream-metrics/stream-health-GMOTHERSTREAM_2-20231113-101543.csv')
df['timestamp_dt'] = pd.to_datetime(df['timestamp_str'])

# Plot health score over time
plt.figure(figsize=(12, 6))
plt.plot(df['timestamp_dt'], df['health_score'])
plt.axhline(y=70, color='r', linestyle='--', label='Acceptable Threshold')
plt.xlabel('Time')
plt.ylabel('Health Score')
plt.title('Stream Health Over Time')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig('stream-health-timeline.png')
```

## Integration with Existing Monitoring

This complements the OBS monitoring tool (`obs-stream-switch-monitor.py`):

**OBS Monitor** - Focuses on:
- Source state transitions
- Problematic visibility timing
- Frozen frame detection during switches

**Stream Health Monitor** - Focuses on:
- Continuous health metrics
- Performance trends
- Ongoing playback issues
- System resource impact

Use both together for complete visibility!

## Performance Impact

**CPU Usage**: Negligible (~0.1% per poll)
**Network**: None (local OBS WebSocket queries only)
**Disk I/O**: Minimal (one CSV line per second)
**Memory**: ~1MB for 100 snapshots

**Safe for production use!**

## Troubleshooting

### Monitoring Not Starting

**Check:**
```bash
# Is monitoring integration enabled?
tail logs/motherstream.log | grep "Stream health monitoring"

# Should see: "Stream health monitoring integration enabled"
```

### No Data in CSV

**Causes:**
- Source name doesn't exist
- OBS WebSocket not connected
- Monitoring stopped too quickly

**Fix:**
```bash
# Verify source exists
curl http://localhost:8000/obs/list-inputs | grep GMOTHERSTREAM

# Check OBS connection
curl http://localhost:8000/obs/connection-health
```

### High CPU Usage

**Cause**: Poll interval too aggressive

**Fix:**
```bash
# Increase interval to 2 seconds
curl -X POST "http://localhost:8000/stream-health/configure?poll_interval=2.0"
```

## API Reference Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stream-health/current` | GET | Get latest health snapshot |
| `/stream-health/history?count=N` | GET | Get last N snapshots |
| `/stream-health/status` | GET | Get monitoring system status |
| `/stream-health/configure?poll_interval=X` | POST | Set poll interval |
| `/stream-health/stop` | POST | Stop monitoring & generate report |

## Files Generated

All files stored in: `logs/stream-metrics/`

- `stream-health-SOURCENAME-TIMESTAMP.csv` - Raw metrics data
- `stream-health-SOURCENAME-TIMESTAMP-report.txt` - Analysis report

Keep these files for:
- Historical comparison
- Trend analysis
- Troubleshooting past issues
- Performance documentation

## Next Steps

1. **Start Monitoring**: It's automatic! Just switch streams normally
2. **Watch Health**: Use `curl http://localhost:8000/stream-health/current`
3. **Review Reports**: Check generated reports after each session
4. **Adjust Pipeline**: If issues found, adjust GStreamer pipeline or network
5. **Compare Results**: Monitor before/after changes to verify improvements

The key to smooth playback is **data-driven diagnosis**. This system gives you that data! 📊

