#!/bin/bash

# GST_DEBUG=3 gst-launch-1.0 -v -e \
#     rtmpsrc location=rtmp://localhost:1935/live/Q5K44CZ5WD ! \
#     flvdemux name=demux \
#     demux.audio ! queue ! decodebin ! audioconvert ! audioresample ! voaacenc bitrate=128000 ! queue ! mux. \
#     demux.video ! queue ! identity silent=false ! mux. \
#     flvmux name=mux streamable=true ! \
#     rtmpsink location=rtmp://localhost:1935/motherstream/live




# ffmpeg -loglevel info -rw_timeout 4000000 -probesize 100M -analyzeduration 20M -re \
#     -i rtmp://localhost:1935/live/Q5K44CZ5WD \
#     -c copy \
#     -f flv rtmp://localhost:1935/motherstream/live

# ffmpeg -y -f rawvideo -pix_fmt rgb32 -s 1920x1080 -i /dev/zero -r 30 -i rtmp://localhost:1935/live/Q5K44CZ5WD -filter_complex '[0:][1:]overlay[o1]' -c:v libx264 -g 30 -r 30 -crf 18 -map '[o1]' -f flv rtmp://localhost:1935/motherstream/live

ffmpeg -y \
  -f rawvideo -pix_fmt rgb32 -s 1920x1080 -i /dev/zero -r 30 \
  -i rtmp://localhost:1935/live/Q5K44CZ5WD \
  -filter_complex "\
    [0]drawtext=text='%{gmtime}':x=100:y=50:fontsize=24:fontcolor=yellow:box=1:boxcolor=red[o1]; \
    [o1][1:v]overlay=shortest=0[o2]; \
    [1:a]afifo[a1]" \
  -c:v libx264 -g 30 -r 30 -crf 18 \
  -map "[o2]" -map "[a1]" \
  -f flv rtmp://localhost:1935/motherstream/live

