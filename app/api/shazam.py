import asyncio
import subprocess
import sys
import json
from shazamio import Shazam
from io import BytesIO
import wave
import time
import logging

logger = logging.getLogger(__name__)

# Configuration Constants
RATE = 44100           # Sample rate
CHANNELS = 1           # Number of audio channels
SECONDS = 10           # Duration to buffer before sending to Shazam
FFMPEG_INPUT = "rtmp://192.168.1.100:1935/live/PJNUF61UGN"  # Replace with your RTMP input
FFMPEG_OUTPUT = "pipe:1"  # Output to stdout

async def recognize_song(shazam, audio_data):
    """
    Recognize song using Shazamio.

    :param shazam: An instance of Shazam.
    :param audio_data: Byte data of the WAV audio.
    """
    try:
        # Use the correct method: recognize_song
        out = await shazam.recognize(audio_data)
        print(json.dumps(out, indent=2))
    except Exception as e:
        print(f"Error recognizing song: {e}", file=sys.stderr)

def create_ffmpeg_process(input_url):
    """
    Create and return an FFmpeg subprocess configured to capture audio from the RTMP stream.

    :param input_url: The RTMP stream URL.
    :return: An FFmpeg subprocess.
    """
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', input_url,
        '-vn',                      # Disable video
        '-ac', str(CHANNELS),       # Set number of audio channels
        '-ar', str(RATE),           # Set audio sampling rate
        '-f', 's16le',              # Output raw PCM data
        'pipe:1'                    # Output to stdout
    ]

    process = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # Suppress FFmpeg stderr output
        bufsize=10**8               # Large buffer size to prevent blocking
    )
    return process

def pcm_to_wav(pcm_data):
    """
    Convert raw PCM data to WAV format.

    :param pcm_data: Raw PCM byte data.
    :return: WAV formatted byte data.
    """
    wav_buffer = BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit audio
        wf.setframerate(RATE)
        wf.writeframes(pcm_data)
    wav_buffer.seek(0)
    return wav_buffer.read()

async def stream_audio_to_shazam(process, shazam):
    """
    Stream audio data from FFmpeg process to Shazam for recognition.

    :param process: FFmpeg subprocess.
    :param shazam: An instance of Shazam.
    """
    buffer = BytesIO()
    bytes_per_second = RATE * CHANNELS * 2  # 16-bit audio
    total_bytes = SECONDS * bytes_per_second

    try:
        while True:
            chunk = process.stdout.read(4096)  # Read in small chunks
            if not chunk:
                print("No more data from FFmpeg.", file=sys.stderr)
                break

            buffer.write(chunk)

            if buffer.tell() >= total_bytes:
                # Extract the PCM data for the specified duration
                buffer.seek(0)
                pcm_data = buffer.read(total_bytes)
                buffer = BytesIO()  # Reset buffer for next iteration

                # Convert PCM to WAV
                wav_data = pcm_to_wav(pcm_data)

                # Pass WAV data to Shazamio
                await recognize_song(shazam, wav_data)

                print("Sleeping.")
                time.sleep(10)

    except asyncio.CancelledError:
        print("Streaming cancelled.", file=sys.stderr)
    finally:
        process.terminate()
        process.wait()

async def main():
    """
    Main coroutine to set up FFmpeg and start streaming to Shazam.
    """
    shazam = Shazam()
    process = create_ffmpeg_process(FFMPEG_INPUT)
    
    if not process.stdout:
        print("Failed to open FFmpeg stdout.", file=sys.stderr)
        return

    await stream_audio_to_shazam(process, shazam)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user.", file=sys.stderr)