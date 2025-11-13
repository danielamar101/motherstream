# What is the purpose of this file

This file is here to talk a bit about [gstreamer](https://github.com/GStreamer/gstreamer). Gstreamer is an "open-source multimedia framework" for streaming media. 

We care about it because it can seem to handle stream reconnections better than OBS's built in sources.

- Install [obs-gstreamer](https://obsproject.com/forum/resources/obs-gstreamer.696/) for use with OBS.


- Once it is up and running create a gstreamer source in OBS.

- The following gstreamer pipeline will display a stream and will properly handle reconnects:

**Production (handles timestamp sync issues - RECOMMENDED):**
```
rtmpsrc location=rtmp://<address>/app/key do-timestamp=true ! decodebin name=d d. ! queue max-size-buffers=3 leaky=downstream ! videoscale ! video/x-raw,width=1920,height=1080 ! videoconvert ! clocksync ! video.sink d. ! queue max-size-buffers=200 leaky=downstream ! audioconvert ! audioresample ! audio/x-raw,rate=48000,channels=2 ! clocksync ! audio.sink
```

**Simplified (if you don't experience audio lag):**
```
rtmpsrc location=rtmp://<address>/app/key ! decodebin name=d d. ! queue ! videoscale ! video/x-raw,width=1920,height=1080 ! videoconvert ! video.sink d. ! queue ! audioconvert ! audio.sink
```

**Basic (minimal, no scaling):**
```
rtmpsrc location=rtmp://<address>/app/key ! decodebin name=d d. ! queue ! videoconvert ! video.sink d. ! queue ! audioconvert ! audio.sink
```

**Understanding the Production Pipeline:**

**Timestamp Handling (fixes choppy playback):**
- `do-timestamp=true` - rtmpsrc generates proper timestamps from network packets
- `clocksync` - Synchronizes to prevent audio/video drift
- Eliminates "audio lagging" warnings in OBS

**Queue Configuration (prevents lag buildup):**
- `max-size-buffers=3` - Video buffer (small = responsive)
- `max-size-buffers=200` - Audio buffer (larger = smooth)
- `leaky=downstream` - **Key feature**: drops old data instead of accumulating lag

**Audio Normalization:**
- `audioresample` - Handles different sample rates
- `rate=48000,channels=2` - Standard 48kHz stereo for OBS

**When to Use Each:**
- **Production** - If you see "audio lagging" warnings in OBS logs (use this!)
- **Simplified** - For testing or if streams work perfectly
- **Basic** - Legacy, not recommended for production

**Common Issues Fixed:**
- ✅ "Source X audio is lagging (over by XXX ms)" warnings
- ✅ Choppy/stuttering playback
- ✅ Audio/video desync
- ✅ Buffer buildup causing delays

- [rtmp2](https://gstreamer.freedesktop.org/documentation/rtmp2/rtmp2src.html?gi-language=c)
