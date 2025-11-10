# 🚀 Getting Started with E2E Stress Tests

**5-minute quick start guide for real-world RTMP stream testing**

## ⚡ Super Quick Start (30 seconds)

```bash
cd tests/e2e

# Download test videos (3 different videos for variety)
./scripts/download-test-video.sh

# Run quick verification test (creates users automatically!)
./quick-test.sh
```

That's it! The script will:
1. ✅ Create 10 test users via API automatically
2. ✅ Assign each user a different video
3. ✅ Run the stress test

If that works, your setup is ready. 🎉

---

## 📚 What Are These Tests?

These are **end-to-end tests** that use **real RTMP video streams** to validate that all the race condition fixes work in production-like conditions.

Unlike unit tests (which test code logic), these tests:
- ✅ Use actual ffmpeg to stream video
- ✅ Connect to real RTMP server
- ✅ Simulate 10 concurrent users
- ✅ Test real-world timing and chaos

---

## 🎯 Available Test Scenarios

### 1️⃣ Quick Test (30s) - Start Here!

Verifies your setup works. Runs the simultaneous connection test.

```bash
./quick-test.sh
```

**Good for:** First-time setup validation

---

### 2️⃣ Simultaneous (30s)

All 10 users connect at exact same time.

```bash
./motherstream-stress-test.sh simultaneous
```

**Tests:** Double-start race condition  
**Good for:** Quick verification that atomic operations work

---

### 3️⃣ Orderly (10 minutes)

Users take turns, each streaming for 60 seconds.

```bash
./motherstream-stress-test.sh orderly
```

**Tests:** Stream switching, queue management  
**Good for:** Testing sequential handoffs

---

### 4️⃣ Chaos (3 minutes)

Random start times, random durations, random reconnects.

```bash
./motherstream-stress-test.sh chaos
```

**Tests:** All race conditions under unpredictable load  
**Good for:** Real-world stress testing

---

### 5️⃣ Rapid Reconnect (2 minutes)

Users repeatedly connect/disconnect.

```bash
./motherstream-stress-test.sh rapid-reconnect
```

**Tests:** State consistency, no duplicates  
**Good for:** Testing reconnection logic

---

### 6️⃣ Queue Drain (3 minutes)

Build queue, then empty it one by one.

```bash
./motherstream-stress-test.sh queue-drain
```

**Tests:** Empty queue handling, OBS state  
**Good for:** Testing cleanup logic

---

### 7️⃣ All (20 minutes)

Runs all scenarios sequentially.

```bash
./motherstream-stress-test.sh all
```

**Tests:** Everything  
**Good for:** Pre-production comprehensive validation

---

## 📊 Interpreting Results

### ✅ Success Looks Like:

```
[2025-11-10 15:30:53] [SUCCESS] ✓ All 10 users in queue
[2025-11-10 15:31:05] [SUCCESS] ✓ Simultaneous start scenario complete
```

Key indicators:
- No ERROR messages
- Queue length matches expected
- All users accounted for
- Smooth transitions

### ❌ Failure Looks Like:

```
[2025-11-10 15:30:53] [ERROR] Queue corruption detected
[2025-11-10 15:31:05] [WARNING] User 5 missing from queue
```

Key indicators:
- ERROR in logs
- Wrong queue length
- Missing users
- Application crash

---

## 🔍 Viewing Logs

```bash
# View latest results
cat logs/results-*.log

# View last 50 lines
tail -50 logs/results-*.log

# Check for errors
grep ERROR logs/results-*.log

# View specific user's stream
cat logs/user1.log
```

---

## 🛠️ Requirements

### Must Have:
- **ffmpeg** - `sudo apt install ffmpeg`
- **curl** - Usually pre-installed
- **Test video** - Run `./scripts/download-test-video.sh`

### Nice to Have:
- **jq** - `sudo apt install jq` (for pretty queue state)

---

## 🎬 Example Session

```bash
# First time setup
cd tests/e2e
./scripts/download-test-video.sh

# Quick verification (30s)
./quick-test.sh
# ✅ Success! Setup is working

# Run a real test (3 minutes)
./motherstream-stress-test.sh chaos
# ✅ Chaos mode complete! No errors found

# Run comprehensive suite (20 minutes)
./motherstream-stress-test.sh all
# ✅ All scenarios passed!

# Check results
cat logs/results-*.log | tail -100
```

---

## 🌍 Testing Staging vs Production

### Staging:
```bash
ENV=STAGE ./motherstream-stress-test.sh simultaneous
```

### Production (default):
```bash
./motherstream-stress-test.sh simultaneous
```

---

## ⚙️ Configuration

Edit `motherstream-stress-test.sh` to customize:

```bash
NUM_USERS=10              # Number of concurrent users
ORDERLY_DURATION=60       # Seconds per user (orderly mode)
CHAOS_MIN_DURATION=15     # Min duration (chaos mode)
CHAOS_MAX_DURATION=90     # Max duration (chaos mode)
```

---

## 🐛 Common Issues

### "Video file not found"
```bash
./scripts/download-test-video.sh
```

### "ffmpeg not found"
```bash
sudo apt install ffmpeg
```

### "Connection refused"
- Verify motherstream server is running
- Check HOST in script matches your server

### Streams won't start
- Check stream keys are valid
- Verify firewall allows RTMP (port 1935)

---

## 📖 Next Steps

1. ✅ Run `./quick-test.sh` to verify setup
2. ✅ Run individual scenarios to understand each test
3. ✅ Run `./motherstream-stress-test.sh all` before deployment
4. ✅ Add to CI/CD pipeline
5. ✅ Read full documentation in `README.md`

---

## 🎓 Integration with Other Tests

| Test Type | Command | Duration | When to Run |
|-----------|---------|----------|-------------|
| Unit | `make test-unit` | 5s | Every code change |
| Integration | `make test-integration` | 15s | Before commit |
| Stress | `make test-stress` | 2min | Before PR |
| **E2E** | `./quick-test.sh` | **30s** | **Before deploy** |
| **E2E Full** | `./motherstream-stress-test.sh all` | **20min** | **Weekly/Release** |

---

## 🏆 Success!

If you've made it here and tests are passing, congratulations! 🎉

Your motherstream application is:
- ✅ Bulletproof against race conditions
- ✅ Validated with real RTMP streams
- ✅ Ready for production deployment

---

**Questions? See `README.md` for complete documentation.**

