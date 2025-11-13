# OBS Stream Switch Monitoring

Tools for diagnosing timing issues during stream switches by monitoring OBS source health in real-time.

## Problem Being Investigated

During stream switches, the GMOTHERSTREAM source may become visible before it's fully initialized, causing frozen frames. This monitoring tool captures the exact timing of:
- Media source state changes (STOPPED → BUFFERING → PLAYING)
- Source visibility changes (hidden → visible)
- Problematic transitions (visible while not PLAYING)

## Files

- **`obs-stream-switch-monitor.py`** - Main monitoring script
- **`run-monitored-test.sh`** - Helper wrapper to run tests with monitoring
- **`README-obs-monitoring.md`** - This documentation

## Prerequisites

### Environment Variables

The monitor reads OBS credentials from environment variables:

```bash
export OBS_HOST=localhost          # OBS WebSocket host
export OBS_PORT=4455              # OBS WebSocket port
export OBS_PASSWORD=your_password  # OBS WebSocket password
```

Or load from `.env.prod`:
```bash
export $(grep -E "^OBS_" .env.prod | xargs)
```

### Python Dependencies

The monitor uses the same `obswebsocket` library as the main application:
```bash
pip install obs-websocket-py websocket-client
```

## Usage

### Option 1: Standalone Monitoring (Manual Test)

Start the monitor, then manually trigger stream switches:

```bash
# Start monitoring with default settings (200ms poll interval)
python3 tests/e2e/obs-stream-switch-monitor.py

# Monitor with custom poll interval (slower = less OBS load)
python3 tests/e2e/obs-stream-switch-monitor.py --poll-interval 0.5

# Monitor with custom output location
python3 tests/e2e/obs-stream-switch-monitor.py --output logs/my-test.csv
```

Then in another terminal, trigger stream switches manually or run tests. The monitor runs until you press Ctrl+C.

### Option 2: Automated Test + Monitoring

Use the wrapper script to automatically run tests with monitoring:

```bash
# Run orderly scenario with monitoring (recommended)
./tests/e2e/run-monitored-test.sh orderly

# Run chaos scenario with slower polling
./tests/e2e/run-monitored-test.sh chaos 0.3

# Available scenarios: simultaneous, orderly, chaos, rapid-reconnect, queue-drain
```

The wrapper script:
1. Loads OBS credentials from `.env.prod`
2. Starts the monitor in the background
3. Runs your chosen test scenario
4. Stops the monitor gracefully
5. Shows the report summary

## Configuration

### Poll Interval

Control how often the monitor checks OBS state:

| Interval | Frequency | Use Case |
|----------|-----------|----------|
| 0.1s | 10 Hz | High-resolution timing, may stress OBS |
| 0.2s | 5 Hz | **Default** - Good balance |
| 0.5s | 2 Hz | Lighter load, may miss quick transitions |
| 1.0s | 1 Hz | Minimal load, for long tests |

Adjust via `--poll-interval` argument:
```bash
python3 tests/e2e/obs-stream-switch-monitor.py --poll-interval 0.5
```

### Source and Scene Names

The monitor watches:
- **Source**: `GMOTHERSTREAM`
- **Scene**: `MOTHERSTREAM`

These are hardcoded in the script. To monitor different sources, edit the constants at the top of `obs-stream-switch-monitor.py`:

```python
SOURCE_NAME = "GMOTHERSTREAM"
SCENE_NAME = "MOTHERSTREAM"
```

## Output

### CSV File

Detailed timeline data: `logs/obs-monitor-TIMESTAMP.csv`

Columns:
- **Timestamp** - Human-readable time with milliseconds
- **Timestamp_Float** - Unix timestamp for calculations
- **Poll_Count** - Sequential poll number
- **Event_Type** - Type of change detected
- **Visibility** - True (visible) or False (hidden)
- **Media_State** - OBS media state (PLAYING, BUFFERING, STOPPED, etc.)
- **Notes** - Details about state transitions

Example:
```csv
Timestamp,Timestamp_Float,Poll_Count,Event_Type,Visibility,Media_State,Notes
2025-11-11 14:23:01.234,1731342181.234,1,INITIAL_STATE,False,PLAYING,Monitoring started
2025-11-11 14:23:05.456,1731342185.456,22,MEDIA_STATE_CHANGE,False,STOPPED,MediaState: PLAYING → STOPPED
2025-11-11 14:23:07.891,1731342187.891,34,VISIBILITY_CHANGE,True,BUFFERING,⚠️ PROBLEM: Source visible while in BUFFERING state!
```

### Report File

Summary analysis: `logs/obs-monitor-TIMESTAMP-report.txt`

Contains:
- Statistics (total polls, state changes, problems detected)
- List of problematic transitions with timestamps
- Conclusion about whether hypothesis is confirmed
- Detailed timeline of all state changes

### Console Output

Real-time state changes with color coding:
- 🟢 **Green** - PLAYING state (healthy)
- 🟡 **Yellow** - Other states (buffering, stopped)
- 🔴 **Red** - Problematic transitions (visible + not playing)

## Interpreting Results

### If Hypothesis is CORRECT

You'll see patterns like:
```
[14:23:05.456] MEDIA_STATE_CHANGE  | 🙈 HIDDEN | 📺 STOPPED      | MediaState: PLAYING → STOPPED
[14:23:07.891] VISIBILITY_CHANGE   | 👁 VISIBLE | 📺 BUFFERING    | ⚠️ PROBLEM: Source visible while in BUFFERING state!
[14:23:12.345] MEDIA_STATE_CHANGE  | 👁 VISIBLE | 📺 PLAYING      | MediaState: BUFFERING → PLAYING
```

**Meaning**: Source became visible ~5 seconds before it was ready to play, causing frozen frames.

**Report will say**: "PROBLEMATIC TRANSITIONS DETECTED - Source is becoming visible before it's ready!"

### If Hypothesis is INCORRECT

You'll see patterns like:
```
[14:23:05.456] MEDIA_STATE_CHANGE  | 🙈 HIDDEN | 📺 STOPPED      | MediaState: PLAYING → STOPPED
[14:23:06.123] MEDIA_STATE_CHANGE  | 🙈 HIDDEN | 📺 PLAYING      | MediaState: STOPPED → PLAYING
[14:23:08.456] VISIBILITY_CHANGE   | 👁 VISIBLE | 📺 PLAYING      | Visibility: hidden → visible
```

**Meaning**: Source became PLAYING before it became visible. Timing is correct.

**Report will say**: "NO PROBLEMATIC TRANSITIONS DETECTED - The hypothesis may be incorrect."

## Timing Metrics to Look For

### Key Questions

1. **How long from restart trigger to PLAYING?**
   - Look for time between STOPPED and PLAYING states
   - This is the actual initialization time

2. **How long from restart trigger to visible?**
   - Look for time between STOPPED and visibility change
   - Compare to initialization time

3. **Is source visible while not PLAYING?**
   - Problematic transitions count in report
   - If > 0, confirms the hypothesis

### Example Analysis

```
14:23:05.456 - Source goes STOPPED (restart triggered)
14:23:12.345 - Source goes PLAYING (6.9 seconds later)
14:23:07.891 - Source becomes visible (2.4 seconds after restart)
```

**Problem**: Source became visible 4.5 seconds before it was ready!

**Solution needed**: Either:
- Wait longer before making visible (>7 seconds)
- Poll media state and only make visible when PLAYING
- Keep source hidden during restart

## Troubleshooting

### Monitor won't connect to OBS

```
✗ Failed to connect to OBS: [Errno 111] Connection refused
```

**Fixes**:
- Ensure OBS is running
- Check OBS WebSocket server is enabled (Tools → WebSocket Server Settings)
- Verify OBS_HOST, OBS_PORT, OBS_PASSWORD are correct
- Test connection: `curl http://localhost:4455` (should respond)

### No state changes detected

**Possible causes**:
- Source doesn't exist (check SOURCE_NAME matches OBS)
- Scene doesn't exist (check SCENE_NAME matches OBS)
- No stream switches occurred during monitoring
- Source is in a scene that's not active

**Fixes**:
- List all inputs: `curl http://localhost:8000/obs/list-inputs`
- Verify source exists and is named "GMOTHERSTREAM"
- Ensure stream switches happen during monitoring window

### High CPU usage / OBS lag

**Cause**: Polling too frequently

**Fix**: Increase poll interval:
```bash
python3 tests/e2e/obs-stream-switch-monitor.py --poll-interval 0.5
```

Or use the wrapper with slower polling:
```bash
./tests/e2e/run-monitored-test.sh orderly 0.5
```

### Connection keeps dropping

The monitor will automatically attempt to reconnect. If it fails repeatedly:
- Check OBS logs for WebSocket errors
- Ensure OBS is stable (not crashing)
- Reduce poll frequency to reduce load

## Advanced Usage

### Monitoring Multiple Tests

Run a series of tests with monitoring:

```bash
for scenario in orderly chaos rapid-reconnect; do
    echo "Testing $scenario..."
    ./tests/e2e/run-monitored-test.sh $scenario 0.2
    sleep 10  # Cooldown between tests
done
```

### Custom Analysis

The CSV output can be imported into spreadsheets or analyzed with Python:

```python
import pandas as pd

# Load monitoring data
df = pd.read_csv('logs/obs-monitor-20251111-142301.csv')

# Find all problematic transitions
problems = df[df['Notes'].str.contains('PROBLEM', na=False)]
print(f"Found {len(problems)} problematic transitions")

# Calculate average time from STOPPED to PLAYING
# (implementation left as exercise)
```

### Long-Running Monitoring

Monitor for an extended period to catch rare issues:

```bash
# Start monitor
python3 tests/e2e/obs-stream-switch-monitor.py --poll-interval 0.5 &
MONITOR_PID=$!

# Let it run for hours while system operates normally
# ...

# Stop when done
kill -INT $MONITOR_PID
```

## Next Steps After Diagnosis

### If Problems Are Confirmed

Implement one of these solutions in the code:

1. **Increase delay after restart** (simple)
   - Update `OBS_JOB_DELAY` in `app/core/worker.py`
   - Add extra delay specifically for `RESTART_MEDIA_SOURCE` jobs

2. **Keep source hidden during restart** (recommended)
   - Modify job sequence in `app/core/process_manager.py`:
     ```python
     # Turn off first
     add_job(JobType.TOGGLE_OBS_SRC, payload={"source_name": "GMOTHERSTREAM", "only_off": True})
     # Then restart while hidden
     add_job(JobType.RESTART_MEDIA_SOURCE, payload={"source_name": "GMOTHERSTREAM"})
     # Wait, then turn on
     add_job(JobType.TOGGLE_OBS_SRC, payload={"source_name": "GMOTHERSTREAM", "only_off": False})
     ```

3. **Poll for readiness** (most robust)
   - Modify `restart_media_source()` in `app/obs.py` to poll `GetMediaInputStatus`
   - Wait for `mediaState` to be "PLAYING" before returning
   - Set timeout (e.g., 15 seconds based on observed initialization time)

### If No Problems Are Found

Look elsewhere for the frozen frame issue:
- SRS stream switching timing
- GStreamer pipeline configuration
- OBS scene transition effects
- Network buffering issues

## Support

If you encounter issues with the monitoring tools:
1. Check OBS WebSocket connection manually
2. Review monitor console output for errors
3. Examine generated CSV file for data quality
4. Test with slower poll intervals

For issues with the main application or stream switching, see the main project documentation.

