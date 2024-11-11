# GST_DEBUG=3 gst-launch-1.0 -e \
#     rtmpsrc location="rtmp://localhost:1935/live/Q5K44CZ5WD" ! \
#     flvdemux name=demux \
#     demux.audio ! queue ! audioconvert ! audioresample ! voaacenc bitrate=128000 ! queue ! mux. \
#     demux.video ! queue ! videoconvert ! x264enc bitrate=6000 speed-preset=veryfast ! video/x-h264,profile=baseline ! queue ! mux. \
#     flvmux name=mux streamable=true ! \
#     rtmpsink location="rtmp://localhost:1935/motherstream/live"

GST_DEBUG=3 gst-launch-1.0 -e \
    rtmpsrc location="rtmp://localhost:1935/live/Q5K44CZ5WD" ! \
    flvdemux name=demux \
    demux.audio ! queue ! decodebin ! audioconvert ! audioresample ! voaacenc bitrate=28000 ! queue ! mux. \
    demux.video ! queue ! decodebin ! videoconvert ! x264enc bitrate=1000 speed-preset=veryfast ! video/x-h264,profile=baseline ! queue ! mux. \
    flvmux name=mux streamable=true ! \
    rtmpsink location="rtmp://localhost:1935/motherstream/live"