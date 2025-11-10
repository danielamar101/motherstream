# 🎬 Motherstream E2E Stress Tests

End-to-end stress testing suite for motherstream using real RTMP streams.

## 🎯 Purpose

These tests validate that all race condition fixes work correctly with **real RTMP streams**, not just unit tests. They simulate actual user behavior including:

- Multiple concurrent connections
- Stream switching
- Disconnect/reconnect cycles
- Unpredictable timing (chaos mode)
- Queue building and draining

## 🏗️ What This Tests

### All 6 Race Conditions Under Real Load

1. ✅ **File I/O Inside Lock** - Concurrent operations don't block
2. ✅ **Duplicate Queue Entries** - Atomic add-if-not-exists works
3. ✅ **Concurrent switch_stream** - Non-reentrant lock prevents double-switch
4. ✅ **Stale Reads** - Queue state remains consistent during modifications
5. ✅ **Double-Start Race** - Only one user forwards when queue empty
6. ✅ **Continuous Job Enqueueing** - OBS flag prevents duplicate jobs

## 📁 Directory Structure

```
tests/e2e/
├── motherstream-stress-test.sh    # Main stress test script
├── scripts/
│   └── download-test-video.sh     # Download test video
├── videos/                         # Test video files (gitignored)
│   └── test-video.mp4
├── logs/                           # Test logs (gitignored)
│   ├── results-YYYYMMDD-HHMMSS.log
│   ├── user1.log
│   ├── user2.log
│   └── ...
└── README.md                       # This file
```

## 🚀 Quick Start

### 1. Download Test Videos

```bash
cd tests/e2e
./scripts/download-test-video.sh
```

This downloads **3 different test videos** for variety (each user streams a different video). Alternatively, use your own MP4 files:

```bash
cp /path/to/your/videos/*.mp4 videos/
```

**Note:** Each of the 10 test users will cycle through available videos for more realistic testing.

### 2. Run a Test Scenario

**Test users are created automatically via API!** No manual setup needed.

```bash
# Run orderly rotation test (10 minutes)
./motherstream-stress-test.sh orderly

# Run simultaneous connection test (30 seconds)
./motherstream-stress-test.sh simultaneous

# Run chaos mode (3 minutes)
./motherstream-stress-test.sh chaos

# Run all scenarios (15-20 minutes)
./motherstream-stress-test.sh all
```

On first run, the script will automatically create 10 test users via the API:
- `stresstest1@motherstream.test` through `stresstest10@motherstream.test`
- Each with unique DJ names and stream keys
- Users are saved and reused on subsequent runs

## 📊 Test Scenarios

### 1. Simultaneous Start (~30 seconds)

**Tests:** Double-start race condition

All 10 users connect at the exact same time.

**Expected Result:**
- Only 1 user forwards
- 9 users queue
- All 10 appear in queue

**Validates:**
- Atomic `on_publish` checks work
- No race condition in initial queue building

```bash
./motherstream-stress-test.sh simultaneous
```

---

### 2. Orderly Rotation (~10 minutes)

**Tests:** `switch_stream` non-reentrant lock, queue management

Each user streams for exactly 60 seconds, then disconnects. Next user takes over.

**Expected Result:**
- Smooth transitions every 60 seconds
- Queue order maintained
- No missed switches

**Validates:**
- `switch_stream` can't be called twice simultaneously
- Queue properly dequeues and promotes users
- State transitions are clean

```bash
./motherstream-stress-test.sh orderly
```

---

### 3. Chaos Mode (~3 minutes)

**Tests:** All race conditions simultaneously

Random start times (0-30s apart), random durations (15-90s), some users reconnect immediately after disconnect.

**Expected Result:**
- System remains stable
- No crashes or hangs
- Queue integrity maintained

**Validates:**
- System handles unpredictable real-world behavior
- All race condition fixes hold under stress
- Concurrent operations don't corrupt state

```bash
./motherstream-stress-test.sh chaos
```

---

### 4. Rapid Reconnect (~2 minutes)

**Tests:** Stale reads, duplicate detection

Users connect for 10 seconds, disconnect, wait 3 seconds, reconnect. Repeat 5 times.

**Expected Result:**
- No duplicate entries in queue
- State remains consistent
- All reconnects succeed

**Validates:**
- `queue_client_stream_if_not_exists` atomic operation
- No stale reads during queue modifications
- Proper cleanup on disconnect

```bash
./motherstream-stress-test.sh rapid-reconnect
```

---

### 5. Queue Drain (~3 minutes)

**Tests:** Empty queue handling, OBS state management

Build up queue with 10 users, then gradually disconnect one by one until queue is empty.

**Expected Result:**
- Queue drains cleanly to 0
- OBS turns off when empty
- `obs_turned_off_for_empty_queue` flag works

**Validates:**
- Empty queue state is handled correctly
- OBS jobs aren't duplicated when queue empty
- System ready for next user after drain

```bash
./motherstream-stress-test.sh queue-drain
```

---

### 6. All Scenarios (~15-20 minutes)

Runs all scenarios sequentially for comprehensive testing.

```bash
./motherstream-stress-test.sh all
```

## 📋 Prerequisites

### Required Tools

- **ffmpeg** - For streaming video
  ```bash
  sudo apt install ffmpeg
  ```

- **curl** - For API calls (usually pre-installed)

- **jq** - For JSON parsing and user creation
  ```bash
  sudo apt install jq
  ```

### Test Data

- **Videos** - Downloaded automatically via `./scripts/download-test-video.sh`
- **Users** - Created automatically via API on first run (no manual setup!)

### Environment

Set `ENV=STAGE` to test against staging server:

```bash
ENV=STAGE ./motherstream-stress-test.sh simultaneous
```

## 📊 Interpreting Results

### Success Indicators ✅

- **No crashes** - Application stays running
- **No deadlocks** - All operations complete
- **Correct queue length** - Matches expected user count
- **Proper transitions** - Stream switches happen on schedule
- **Clean logs** - No error messages in results

### Failure Indicators ❌

- **Application crash** - Server stops responding
- **Queue corruption** - Wrong number of users or duplicates
- **Missed switches** - Users don't get their turn
- **Stuck state** - Queue not processing
- **Error logs** - Exceptions or race condition warnings

### Example Success Output

```
[2025-11-10 15:30:45] [INFO] Launching all users simultaneously...
[2025-11-10 15:30:53] [INFO] Queue length after simultaneous start: 10
[2025-11-10 15:30:53] [SUCCESS] ✓ All 10 users in queue (race condition handled correctly!)
[2025-11-10 15:31:05] [SUCCESS] ✓ Simultaneous start scenario complete
```

## 📁 Log Files

### Main Results Log

`logs/results-YYYYMMDD-HHMMSS.log` - Complete test results with timestamps

### Individual User Logs

`logs/userN.log` - ffmpeg output for each user

### Viewing Logs

```bash
# View latest results
cat logs/results-*.log | tail -100

# View specific user's stream log
cat logs/user1.log

# Check for errors
grep ERROR logs/results-*.log

# Check for warnings
grep WARNING logs/results-*.log
```

## 🔧 Configuration

Edit variables at top of `motherstream-stress-test.sh`:

```bash
NUM_USERS=10              # Number of concurrent users
ORDERLY_DURATION=60       # Seconds per user in orderly mode
CHAOS_MIN_DURATION=15     # Min stream duration in chaos mode
CHAOS_MAX_DURATION=90     # Max stream duration in chaos mode
```

## 🎓 Best Practices

### Before Running Tests

1. ✅ Ensure motherstream server is running
2. ✅ Verify network connectivity
3. ✅ Download test video
4. ✅ Install ffmpeg and jq

### During Tests

1. 📊 Monitor server logs in another terminal
2. 🔍 Watch queue state on motherstream UI
3. 📈 Check system resources (CPU, memory)

### After Tests

1. 📝 Review results log for anomalies
2. ✅ Verify all scenarios passed
3. 🔍 Check for any ERROR or WARNING messages
4. 🧹 Clean up logs if needed: `rm -rf logs/*`

## 🐛 Troubleshooting

### "Video file not found"

```bash
cd tests/e2e
./scripts/download-test-video.sh
```

### "ffmpeg not found"

```bash
sudo apt install ffmpeg
```

### "jq not found" (optional but recommended)

```bash
sudo apt install jq
```

### Streams won't connect

- Check motherstream server is running
- Verify `HOST` in script matches your server
- Check firewall settings
- Verify stream keys are valid

### Queue API not responding

- Ensure API endpoint exists: `/api/queue`
- Check `API_HOST` in script
- Verify server is accessible

## 🎯 Integration with Unit Tests

These E2E tests **complement** the unit tests:

| Test Type | What It Validates | Speed |
|-----------|-------------------|-------|
| **Unit Tests** | Logic correctness, thread safety | Fast (~5s) |
| **E2E Tests** | Real-world behavior, RTMP streams | Slow (~1-20min) |

**Recommended Testing Strategy:**

1. 🏃 Run unit tests on every code change (fast feedback)
2. 🚀 Run E2E tests before deployment (confidence)
3. 🔥 Run chaos mode in staging (real-world validation)

## 📈 Expected Test Times

| Scenario | Duration | Users | Complexity |
|----------|----------|-------|------------|
| Simultaneous | ~30s | 10 | Low |
| Orderly | ~10min | 10 | Medium |
| Chaos | ~3min | 10 | High |
| Rapid Reconnect | ~2min | 10 | Medium |
| Queue Drain | ~3min | 10 | Medium |
| **All** | **~20min** | **10** | **Complete** |

## 🏆 Success Criteria

Tests pass if:

- ✅ No application crashes
- ✅ No deadlocks (all operations complete)
- ✅ No duplicate users in queue
- ✅ Correct user always forwarding
- ✅ Queue order maintained
- ✅ All state transitions logged correctly
- ✅ OBS state managed properly
- ✅ No race condition errors in logs

## 🚀 CI/CD Integration

Add to your deployment pipeline:

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: |
          sudo apt update
          sudo apt install -y ffmpeg jq
      - name: Download test video
        run: cd tests/e2e && ./scripts/download-test-video.sh
      - name: Run stress tests
        run: cd tests/e2e && ./motherstream-stress-test.sh all
```

## 📚 Additional Resources

- **Unit Tests**: `tests/unit/` - Fast, isolated tests
- **Integration Tests**: `tests/integration/` - Component integration
- **Stress Tests**: `tests/stress/` - High concurrent load
- **E2E Tests**: `tests/e2e/` - Real RTMP streams (this directory)

## 💡 Tips

1. **Start small** - Run `simultaneous` first to verify setup
2. **Monitor server** - Watch logs during tests
3. **Use jq** - Makes queue state much easier to read
4. **Save logs** - Keep successful test logs for comparison
5. **Test staging first** - Before running on production

---

**Your motherstream application is bulletproof! 🛡️**

These E2E tests ensure all race condition fixes work in the real world with actual RTMP streams.

