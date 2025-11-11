import subprocess
import time
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

class StreamHealthChecker:
    """
    Monitors the health of an RTMP output stream using ffprobe.
    Tracks consecutive failures and provides methods to check if stream is unhealthy.
    """
    
    def __init__(self, stream_url: str, unhealthy_threshold_seconds: int = 30):
        self.stream_url = stream_url
        self.unhealthy_threshold_seconds = unhealthy_threshold_seconds
        self.first_failure_time: Optional[float] = None
        self.last_check_time: Optional[float] = None
        self.is_healthy = True
        self.is_checking = False  # Flag to prevent concurrent health checks
        self.lock = threading.Lock()
        
    def check_stream_health(self) -> bool:
        """
        Check if the RTMP stream is healthy using ffprobe.
        Returns True if healthy, False if unhealthy.
        """
        # Check if a health check is already in progress
        with self.lock:
            if self.is_checking:
                logger.debug(f"Health check already in progress for {self.stream_url}, skipping")
                return self.is_healthy
            self.is_checking = True
        
        try:
            # Use ffprobe to check if the stream is accessible
            # -v error: show only errors
            # -show_entries stream=codec_type: show stream types
            # -of csv=p=0: output format without headers
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'stream=codec_type',
                '-of', 'csv=p=0',
                self.stream_url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3  # Reduced timeout from 10s to 3s for faster failure detection
            )
            
            # If ffprobe succeeds and returns stream info, check for video stream
            if result.returncode == 0 and result.stdout.strip():
                # Check if there's at least one video stream
                output_lines = result.stdout.strip().split('\n')
                has_video = any('video' in line for line in output_lines)
                is_healthy = has_video
                logger.debug(f"Stream {self.stream_url} ffprobe output: {output_lines}, has_video: {has_video}")
            else:
                is_healthy = False
                logger.debug(f"Stream {self.stream_url} ffprobe failed: returncode={result.returncode}, stdout='{result.stdout}', stderr='{result.stderr}'")
            
            with self.lock:
                current_time = time.time()
                self.last_check_time = current_time
                
                if is_healthy:
                    # Stream is healthy, reset failure tracking
                    if not self.is_healthy:
                        logger.info(f"Stream {self.stream_url} is now healthy")
                    self.is_healthy = True
                    self.first_failure_time = None
                else:
                    # Stream is unhealthy
                    if self.is_healthy:
                        # First failure detected
                        logger.warning(f"Stream {self.stream_url} health check failed. Starting failure timer.")
                        self.first_failure_time = current_time
                        self.is_healthy = False
                    else:
                        # Continued failure
                        logger.debug(f"Stream {self.stream_url} still unhealthy")
                
                return is_healthy
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Health check timeout for stream {self.stream_url}")
            return self._handle_failure()
        except subprocess.CalledProcessError as e:
            logger.warning(f"Health check failed for stream {self.stream_url}: {e}")
            return self._handle_failure()
        except Exception as e:
            logger.error(f"Unexpected error checking stream health for {self.stream_url}: {e}")
            return self._handle_failure()
        finally:
            # Always clear the checking flag when done
            with self.lock:
                self.is_checking = False
    
    def _handle_failure(self) -> bool:
        """Handle a health check failure and update internal state."""
        with self.lock:
            current_time = time.time()
            self.last_check_time = current_time
            
            if self.is_healthy:
                # First failure detected
                logger.warning(f"Stream {self.stream_url} health check failed. Starting failure timer.")
                self.first_failure_time = current_time
                self.is_healthy = False
            
            return False
    
    def is_unhealthy_for_threshold(self) -> bool:
        """
        Check if the stream has been unhealthy for longer than the threshold.
        Returns True if stream should be considered failed.
        """
        with self.lock:
            if self.is_healthy or self.first_failure_time is None:
                return False
            
            current_time = time.time()
            unhealthy_duration = current_time - self.first_failure_time
            
            return unhealthy_duration >= self.unhealthy_threshold_seconds
    
    def get_unhealthy_duration(self) -> float:
        """Get how long the stream has been unhealthy in seconds."""
        with self.lock:
            if self.is_healthy or self.first_failure_time is None:
                return 0.0
            
            current_time = time.time()
            return current_time - self.first_failure_time
    
    def reset(self):
        """Reset the health checker state."""
        with self.lock:
            self.is_healthy = True
            self.first_failure_time = None
            self.last_check_time = None
            self.is_checking = False  # Reset checking flag
            logger.info(f"Health checker reset for stream {self.stream_url}") 