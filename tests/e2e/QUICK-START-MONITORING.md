# Quick Start: OBS Stream Switch Monitoring

**Goal**: Diagnose if GMOTHERSTREAM becomes visible before it's ready, causing frozen frames.

## Prerequisites

1. **OBS is running** with WebSocket server enabled
2. **Credentials loaded** from `.env.prod`
3. **Python dependencies** installed (uses same libs as main app)

## Step 1: Test Connection

```bash
cd /home/motherstream/Desktop/motherstream
./tests/e2e/test-obs-connection.sh
```

If this fails, fix OBS connection before proceeding.

## Step 2: Run Monitored Test

### Option A: Automated (Recommended)

Run a test with automatic monitoring:

```bash
# Orderly scenario (1 hour, smooth transitions)
./tests/e2e/run-monitored-test.sh orderly

# Chaos scenario (random timings)
./tests/e2e/run-monitored-test.sh chaos

# With slower polling (if OBS is stressed)
./tests/e2e/run-monitored-test.sh orderly 0.5
```

The script will:
- Start monitoring automatically
- Run the test
- Stop monitoring
- Show you the report

### Option B: Manual

In **Terminal 1** (Monitor):
```bash
python3 tests/e2e/obs-stream-switch-monitor.py
```

In **Terminal 2** (Test):
```bash
./tests/e2e/motherstream-stress-test.sh orderly
```

Press **Ctrl+C** in Terminal 1 when done.

## Step 3: Check Results

Look for the report in `tests/e2e/logs/`:

```bash
ls -lt tests/e2e/logs/
```

You'll see:
- `obs-monitor-TIMESTAMP.csv` - Raw data
- `obs-monitor-TIMESTAMP-report.txt` - Analysis

## Step 4: Interpret Results

Open the report file:

```bash
cat tests/e2e/logs/obs-monitor-*-report.txt | tail -30
```

### If You See: "⚠️ PROBLEMATIC TRANSITIONS DETECTED"

**Meaning**: Source became visible before ready!

**Example**:
```
⚠️ PROBLEM: Source visible while in BUFFERING state!
```

**Next Steps**:
1. Note the timing (e.g., "7 seconds from restart to ready")
2. Implement one of the fixes in the main README
3. Run test again to verify fix

### If You See: "✓ NO PROBLEMATIC TRANSITIONS DETECTED"

**Meaning**: Timing looks correct!

**Next Steps**:
- Look elsewhere for frozen frame cause
- Check GStreamer pipeline issues
- Check SRS stream switching
- Check network buffering

## Common Adjustments

### Slower Polling (Less OBS Load)

```bash
# 500ms polling instead of 200ms
./tests/e2e/run-monitored-test.sh orderly 0.5
```

### Longer Test Duration

```bash
# Edit the test script's ORDERLY_DURATION variable
# Or run chaos mode for sustained random testing
./tests/e2e/run-monitored-test.sh chaos
```

### Watch Live

The monitor shows real-time state changes with colors:
- 🟢 Green = PLAYING (good)
- 🟡 Yellow = Other states
- 🔴 Red = Problems detected!

## Troubleshooting

### "Failed to connect to OBS"
- Check OBS is running
- Check Tools → WebSocket Server Settings in OBS
- Verify `.env.prod` has correct credentials

### "No state changes detected"
- Source might not exist or be named wrong
- No stream switches happened during monitoring
- Increase test duration

### "Monitor causes OBS lag"
- Increase poll interval: `--poll-interval 0.5`
- OBS may be under too much load from streams

## Files Created

After running, you'll have:
```
tests/e2e/logs/
├── obs-monitor-20251111-142301.csv        # Timeline data
├── obs-monitor-20251111-142301-report.txt # Analysis
└── results-20251111-142301.log            # Test results
```

## Quick Command Reference

```bash
# Test connection only
./tests/e2e/test-obs-connection.sh

# Run monitored test (easiest)
./tests/e2e/run-monitored-test.sh orderly

# Manual monitoring
python3 tests/e2e/obs-stream-switch-monitor.py

# With custom settings
python3 tests/e2e/obs-stream-switch-monitor.py --poll-interval 0.5 --output logs/my-test.csv

# View latest report
cat tests/e2e/logs/obs-monitor-*-report.txt | tail -50
```

## Expected Timeline (if hypothesis is correct)

You should see something like:

```
[14:23:05.456] MEDIA_STATE_CHANGE  | HIDDEN  | STOPPED → Restart triggered
[14:23:07.891] VISIBILITY_CHANGE   | VISIBLE | BUFFERING → ⚠️ PROBLEM!
[14:23:12.345] MEDIA_STATE_CHANGE  | VISIBLE | PLAYING → Finally ready
```

Time gap = ~7 seconds where source is visible but not ready.

## For More Details

See `tests/e2e/README-obs-monitoring.md` for:
- Detailed configuration options
- Advanced analysis techniques
- Interpretation guidelines
- Implementation recommendations

---

**Ready to diagnose!** Start with `./tests/e2e/test-obs-connection.sh`

