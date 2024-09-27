import requests
import json
import subprocess
import signal
import time
import sys
from threading import Timer

import obspython as obs

vlc_process = None
idle_timeout = 10  # Adjust as necessary

# RTMP stream URL
rtmp_url = "rtmp://192.168.1.100:1935/motherstream/live"

# VLC command with --play-and-exit to close VLC after stream ends
vlc_command = [
    "/Applications/VLC.app/Contents/MacOS/VLC",
    rtmp_url,
    "--play-and-exit",
    "--verbose", "2"  # Increase verbosity to capture errors and stream status
]

def check_for_work():
    '''
    {
        status: "<START|STOP|NOTHING>"
    }
    '''
    body = {
        'status': 'working' if vlc_process else 'idle'
    }
    response = requests.post("http://192.168.1.100:8483/poll-for-work", json=body)
    status = json.loads(response.content)['status']
    return status

# Function to start VLC and track the subprocess
def start_vlc_stream():
    global vlc_command
    print("Starting VLC to play the RTMP stream...")
    process = subprocess.Popen(vlc_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return process

# Function to kill the VLC process if needed
def stop_vlc_stream(process):
    print("Terminating VLC process...")
    process.send_signal(signal.SIGTERM)  
    process.wait()  
    print("VLC process terminated.")

def monitor_vlc(process):
    last_output_time = time.time()

    def check_idle():
        nonlocal last_output_time
        if time.time() - last_output_time > idle_timeout:
            print(f"No activity detected for {idle_timeout} seconds. Terminating VLC process.")
            stop_vlc_stream(process)
            sys.exit(1)

    # Run the idle check periodically
    idle_timer = Timer(idle_timeout, check_idle)
    idle_timer.start()

    while True:
        output = process.stderr.readline()  # Capture VLC stderr output
        if output == '' and process.poll() is not None:
            break  # Process finished
        if output:
            print(output.strip())
            last_output_time = time.time()

            # Error detection
            if "error" in output.lower() or "failed" in output.lower():
                print("Error detected in VLC stream. Terminating process.")
                stop_vlc_stream(process)
                sys.exit(1)

        # Reset the idle timer
        idle_timer.cancel()
        idle_timer = Timer(idle_timeout, check_idle)
        idle_timer.start()

# Main loop
def run_loop():
    global vlc_process
    status = check_for_work()
    print(status)

    if status == 'START':
        if not vlc_process: 
            vlc_process = start_vlc_stream()
            monitor_vlc(vlc_process)  
    elif status == 'KILL':
        if vlc_process:
            stop_vlc_stream(vlc_process)
            vlc_process = None
    else:
        pass

    time.sleep(5)

def script_properties():
    """
    Called to define user properties associated with the script. These
    properties are used to define how to show settings properties to a user.
    """
    obs.timer_add(run_loop, 5)
