import gi
import sys
import threading
import time

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

# Initialize GStreamer
Gst.init(None)

# Define the pipeline
pipeline_description = """
    rtmpsrc location=rtmp://localhost:1935/live/Q5K44CZ5WD ! 
    flvdemux name=demux 
    demux.audio ! queue ! decodebin ! audioconvert ! audioresample ! voaacenc bitrate=128000 ! queue ! mux. 
    demux.video ! queue ! videoconvert ! x264enc bitrate=1000 speed-preset=veryfast ! video/x-h264,profile=baseline ! queue ! mux. 
    flvmux name=mux streamable=true ! rtmpsink location=rtmp://localhost:1935/motherstream/live
"""

# Create the pipeline
pipeline = Gst.parse_launch(pipeline_description)

# Inactivity Timeout Class
class InactivityTimeout:
    def __init__(self, timeout_seconds, on_timeout):
        self.timeout_seconds = timeout_seconds
        self.on_timeout = on_timeout
        self.lock = threading.Lock()
        self.last_activity = time.time()
        self.running = True
        self.thread = threading.Thread(target=self.monitor)
        self.thread.start()

    def reset(self):
        with self.lock:
            self.last_activity = time.time()

    def monitor(self):
        while self.running:
            time.sleep(1)  # Check every second
            with self.lock:
                elapsed = time.time() - self.last_activity
                if elapsed > self.timeout_seconds:
                    print(f"No input received for {self.timeout_seconds} seconds. Stopping pipeline.")
                    self.on_timeout()
                    self.running = False

    def stop(self):
        self.running = False
        self.thread.join()

# Function to handle pipeline timeout
def stop_pipeline():
    pipeline.set_state(Gst.State.NULL)

# Initialize the inactivity timeout (10 seconds)
timeout = InactivityTimeout(10, stop_pipeline)

# Function to add pad probes
def on_buffer(pad, info, data):
    timeout.reset()
    return Gst.PadProbeReturn.OK

def add_probe(element, pad_name):
    pad = element.get_static_pad(pad_name)
    if pad:
        pad.add_probe(Gst.PadProbeType.BUFFER, on_buffer, None)
    else:
        print(f"Pad {pad_name} not found on element {element.get_name()}")

# Add probes to audio and video pads
demux = pipeline.get_by_name("demux")
if not demux:
    print("Demux element not found.")
    sys.exit(1)

add_probe(demux, "audio")
add_probe(demux, "video")  # If applicable

# Listen to the bus
bus = pipeline.get_bus()
bus.add_signal_watch()

def on_message(bus, message):
    t = message.type
    if t == Gst.MessageType.EOS:
        print("End-Of-Stream reached.")
        timeout.stop()
        pipeline.set_state(Gst.State.NULL)
        loop.quit()
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"Error received from element {message.src.get_name()}: {err}")
        print(f"Debugging information: {debug if debug else 'None'}")
        timeout.stop()
        pipeline.set_state(Gst.State.NULL)
        loop.quit()

bus.connect("message", on_message)

# Create a GLib Main Loop
loop = GObject.MainLoop()

# Start playing
pipeline.set_state(Gst.State.PLAYING)

try:
    loop.run()
except:
    pass

# Clean up
pipeline.set_state(Gst.State.NULL)
timeout.stop()