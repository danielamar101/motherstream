# Quick Reference Card - Capacity Testing

## 📋 One-Line Commands

### Basic Capacity Test
```bash
# Terminal 1
./network_monitor.py --interval 5

# Terminal 2  
./stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 50
```

### Analyze Results
```bash
./analyze_monitoring_data.py --latest
```

---

## 🎯 Common Test Scenarios

### Find Maximum Capacity
```bash
./stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 100 --ramp-up 5
```

### Test with Low-Quality Streams
```bash
./stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 200 \
  --resolution 640x360 --fps 24 --bitrate 1000k
```

### Test with High-Quality Streams  
```bash
./stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 20 \
  --resolution 1920x1080 --fps 60 --bitrate 6000k
```

### Sustained Load Test (10 minutes)
```bash
./network_monitor.py --duration 600 &
./stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 50 --monitor-duration 600
```

---

## 📊 Analysis Commands

### View Latest Results
```bash
./analyze_monitoring_data.py --latest
```

### Generate Plot
```bash
./analyze_monitoring_data.py --latest --plot
```

### Save Plot to File
```bash
./analyze_monitoring_data.py --latest --plot --output capacity_report.png
```

### Compare Multiple Tests
```bash
./analyze_monitoring_data.py --compare ./monitoring-logs/network_monitor_*.csv
```

---

## 🔍 What to Look For

### During Test (Terminal 1 - Monitor)

✅ **Healthy System:**
- CPU < 70%
- Memory < 80%
- No network errors
- No bottleneck warnings

⚠️ **Warning Signs:**
- CPU > 80% → Consider CPU upgrade
- Memory > 85% → Add more RAM
- Network errors > 0 → Check network
- High TIME_WAIT → Connection exhaustion

### After Test (Load Tester Report)

✅ **Success:**
- Success Rate > 95%
- Crashed = 0
- Max Concurrent = Target

⚠️ **Capacity Reached:**
- Streams crashing
- Success Rate < 90%
- Max Concurrent < Target

---

## 💡 Quick Tips

1. **Start Small**: Begin with 10-20 streams
2. **Watch Monitor**: Keep Terminal 1 visible during test
3. **Run Multiple Tests**: Get 3-5 samples for accuracy
4. **Set Limits**: Use 70-80% of max in production
5. **Save Reports**: Keep logs for future reference

---

## 🚨 Emergency Stop

Press **Ctrl+C** in both terminals to stop immediately.

---

## 📈 Capacity Estimation

### Bandwidth Calculator
```
Streams × Bitrate = Total Bandwidth

Examples:
- 40 streams × 2.5 Mbps = 100 Mbps
- 100 streams × 2.5 Mbps = 250 Mbps
- 400 streams × 2.5 Mbps = 1000 Mbps (1 Gbps)
```

### Common Limits
- **1 Gbps network**: ~350-400 streams @ 2.5 Mbps
- **10 Gbps network**: ~3500-4000 streams @ 2.5 Mbps
- **CPU (8-core)**: ~30-50 streams per core (encoding dependent)
- **Memory (16GB)**: ~100-200 streams (200MB per stream)

---

## 📁 File Locations

```
scripts/
├── network_monitor.py          # System monitor
├── stream_load_tester.py       # Load tester
├── analyze_monitoring_data.py  # Analysis tool
├── monitoring-logs/            # Output directory
│   ├── network_monitor_*.csv   # Detailed data
│   └── network_summary_*.txt   # Summary reports
└── CAPACITY_TESTING_GUIDE.md   # Full documentation
```

---

## 🎓 Interpreting Results

### Sample Output Interpretation

```
Max Concurrent: 45 streams
Peak Bandwidth: 112.5 Mbps
Bottleneck: CPU (85%)
```

**Means:**
- Your system can handle 45 concurrent streams
- Uses ~112 Mbps upload bandwidth
- CPU is the limiting factor
- Production limit should be ~35 streams (80% of max)

---

## 🔗 Help Commands

```bash
./network_monitor.py --help
./stream_load_tester.py --help
./analyze_monitoring_data.py --help
```

---

## 📞 Troubleshooting One-Liners

```bash
# Check if ffmpeg installed
ffmpeg -version

# Check if psutil installed
python3 -c "import psutil; print('OK')"

# Check RTMP server
curl -I http://localhost:8080/api/v1/streams  # SRS API

# Check open connections
netstat -an | grep 1935 | wc -l

# Check system resources
htop  # or: top

# View recent logs
tail -f ./monitoring-logs/*.csv

# Kill all ffmpeg processes
pkill -9 ffmpeg
```

---

**Print this card and keep it handy! 📄**

