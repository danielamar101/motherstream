# What is the purpose of this file

This file is here to talk a bit about [gstreamer](https://github.com/GStreamer/gstreamer). Gstreamer is an "open-source multimedia framework" for streaming media. 

We care about it because it can seem to handle stream reconnections better than OBS's built in sources.

- Install [obs-gstreamer](https://obsproject.com/forum/resources/obs-gstreamer.696/) for use with OBS.


- Once it is up and running create a gstreamer source in OBS.

- The following gstreamer pipeline will display an stream and will properly handle reconnects:

rtmpsrc location=rtmp://<address>/app/key ! queue max-size-time=1000000000 max-size-bytes=10485760 max-size-buffers=1000 ! decodebin name=bin 
bin. ! queue max-size-time=1000000000 ! videoconvert ! video/x-raw ! video.sink 
bin. ! queue max-size-time=1000000000 ! audioconvert ! audio/x-raw ! audio.sink

- [rtmp2](https://gstreamer.freedesktop.org/documentation/rtmp2/rtmp2src.html?gi-language=c)
