import asyncio
import subprocess
import sys
import json
from shazamio import Shazam
from io import BytesIO
import wave
import time
import logging
import os
import signal

logger = logging.getLogger(__name__)
# ffmpeg process
process = None
# Configuration Constants
RATE = 44100           # Sample rate
CHANNELS = 1           # Number of audio channels
SECONDS = 10           # Duration to buffer before sending to Shazam
FFMPEG_INPUT = "rtmp://always12.duckdns.org/motherstream/live"  # Replace with your RTMP input
SONG_DATA = {}

async def recognize_song(shazam, audio_data):
    """
    Recognize song using Shazamio.

    :param shazam: An instance of Shazam.
    :param audio_data: Byte data of the WAV audio.
    """
    try:
        # Use the correct method: recognize_song
        out = await shazam.recognize(audio_data)
        logger.info(json.dumps(out, indent=2))
        return out
    except Exception as e:
        logger.info(f"Error recognizing song: {e}", file=sys.stderr)

async def create_ffmpeg_process(input_url):
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

    # create subprocess via asyncio
    process = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
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

async def stream_audio_to_shazam(shazam):
    global SONG_DATA
    global process
    """
    Stream audio data from FFmpeg process to Shazam for recognition.

    :param process: FFmpeg subprocess.
    :param shazam: An instance of Shazam.
    """
    bytes_per_second = RATE * CHANNELS * 2  # 16-bit audio
    total_bytes = SECONDS * bytes_per_second
    attempt = 0

    try:
        while True:
            buffer = BytesIO()
            chunk = None
            try:
                chunk = await asyncio.wait_for(process.stdout.read(4096),1) # Read in small chunks, timeout on read if takes too long (non-block)
            except asyncio.TimeoutError:
                logger.info("Timeout trying to read any audio data...")
            if not chunk:
                if attempt == 5:
                    logger.info("Havent gotten any data in a while. Killing this process.")
                    return
                else:
                    attempt += 1
                    continue
            else:
                attempt = 0

            buffer.write(chunk)

            if buffer.tell() >= total_bytes:
                # Extract the PCM data for the specified duration
                buffer.seek(0)
                pcm_data = buffer.read(total_bytes)
                buffer = BytesIO()  # Reset buffer for next iteration

                # Convert PCM to WAV
                wav_data = pcm_to_wav(pcm_data)

                logger.info("Recognizing song.")
                # Pass WAV data to Shazamio
                SONG_DATA = await recognize_song(shazam, wav_data)

                logger.info("Sleeping.")
                await asyncio.sleep(10)

    except asyncio.CancelledError:
        logger.info("Streaming cancelled.", file=sys.stderr)
    finally:
        if process is not None:
            logger.info("Killing the shazam probe...")
            process.terminate()
            process = None
        logger.info("Done killing the shazam probe.")

async def main():
    global process
    global FFMPEG_INPUT
    """
    Main coroutine to set up FFmpeg and start streaming to Shazam.
    """
    shazam = Shazam()
    process = await create_ffmpeg_process(FFMPEG_INPUT)
    
    if not process.stdout:
        logger.error("Failed to open FFmpeg stdout.", file=sys.stderr)
        return

    await stream_audio_to_shazam(shazam)

def recognize_song_full():
    global process
    print(process)
    try:
        if not process:
            asyncio.run(main())
            print("Created task...")
    except KeyboardInterrupt:
        logger.info("Interrupted by user.", file=sys.stderr)

def kill_shazamio_process():
    global process
    try:
        if process is not None and process.poll() is None:  # Check if process exists and is still running
            process.terminate()  # Attempt graceful termination
            process.wait(timeout=5)  # Wait for the process to terminate
            print("FFmpeg process terminated gracefully.")
        else:
            print("No running FFmpeg process to terminate.")
    except Exception as e:
        try:
            # Forcefully kill the process if terminate fails
            if process is not None and process.poll() is None:
                os.kill(process.pid, signal.SIGKILL)
                print("FFmpeg process killed forcefully.")
        except Exception as kill_error:
            print(f"Failed to kill FFmpeg process: {kill_error}")
        print(f"Error during FFmpeg process termination: {e}")
    finally:
        process = None  # Reset the process variable to None


if __name__ == "__main__":
    logging_params = {
        'level': logging.INFO,
        'format': '%(asctime)s__[%(levelname)s, %(module)s.%(funcName)s](%(name)s)__[L%(lineno)d] %(message)s',
    }

    logging.basicConfig(**logging_params)
    try:

        logger.info("Doing something")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.", file=sys.stderr)