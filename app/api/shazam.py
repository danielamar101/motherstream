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
FFMPEG_INPUT = os.getenv("SHAZAM_RTMP_URL", "rtmp://always12.live/motherstream/live")
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
        # logger.info(json.dumps(out, indent=2))
        return out
    except Exception as e:
        logger.info(f"Error recognizing song: {e}")

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

async def stream_audio_to_shazam(myself,process,shazam):
    """
    Stream audio data from FFmpeg process to Shazam for recognition.

    :param process: FFmpeg subprocess.
    :param shazam: An instance of Shazam.
    """
    bytes_per_second = RATE * CHANNELS * 2  # 16-bit audio
    total_bytes = SECONDS * bytes_per_second
    attempt = 0
    buffer = BytesIO()

    try:
        while True:
            chunk = None
            try:
                chunk = await asyncio.wait_for(process.stdout.read(4096),5) # Read in small chunks, timeout on read if takes too long (non-block)
            except asyncio.TimeoutError:
                logger.info("Timeout trying to read any audio data...")
            if chunk is None:
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
                myself.song_data = extract_song_attributes(await recognize_song(shazam, wav_data))

                logger.info("Sleeping.")
                await asyncio.sleep(10)
                buffer = BytesIO()

    except asyncio.CancelledError:
        logger.info("Streaming cancelled.")
    finally:
        if process is not None:
            logger.info("Killing the shazam probe...")
            process.terminate()
            process = None
        logger.info("Done killing the shazam probe.")

async def main(myself):
    global FFMPEG_INPUT
    """
    Main coroutine to set up FFmpeg and start streaming to Shazam.
    """
    shazam = Shazam()
    process = await create_ffmpeg_process(FFMPEG_INPUT)
    
    if not process.stdout:
        logger.error("Failed to open FFmpeg stdout.")
        return

    await stream_audio_to_shazam(myself,process,shazam)

class SongRecognizer:

    song_data = None

    def recognize_song_full(self):
        asyncio.run(main(self))
        logger.info("Created new main task...")


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
        logger.info("Interrupted by user.")


def extract_song_attributes(data):
    # Initialize the result dictionary
    result = {
        'song_name': None,
        'artist': None,
        'label': None,
        'album_cover_link': None,
        'confidence_level': None
    }

    if not data:
        return result

    # Extract song name
    result['song_name'] = data.get('track', {}).get('title')

    # Extract artist
    result['artist'] = data.get('track', {}).get('subtitle')

    # Extract label by searching through sections
    sections = data.get('track', {}).get('sections', [])
    for section in sections:
        if section.get('type') == 'SONG':
            metadata = section.get('metadata', [])
            for item in metadata:
                if item.get('title') == 'Label':
                    result['label'] = item.get('text')
                    break
            if result['label']:
                break

    # Extract album cover link
    result['album_cover_link'] = data.get('track', {}).get('images', {}).get('coverart')

    # Compute confidence level based on matches (if available)
    matches = data.get('matches', [])
    if matches:
        # Example computation: inverse of sum of timeskew and frequencyskew
        # Adjust this formula based on actual confidence metrics
        timeskew = matches[0].get('timeskew', 0)
        frequencyskew = matches[0].get('frequencyskew', 0)
        # Prevent division by zero
        denominator = 1 + timeskew + frequencyskew
        result['confidence_level'] = 1 / denominator if denominator != 0 else None

    return result