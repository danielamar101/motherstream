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
    
    def __init__(self, stream_url: str, unhealthy_threshold_seconds: int = 15):
        self.stream_url = stream_url
        self.unhealthy_threshold_seconds = unhealthy_threshold_seconds
        self.first_failure_time: Optional[float] = None
        self.last_check_time: Optional[float] = None
        self.is_healthy = True
        self.is_checking = False  # Flag to prevent concurrent health checks
        self.enabled = False  # Health checking disabled by default until a stream starts
        self.lock = threading.Lock()
        
    def check_stream_health(self) -> bool:
        """
        Check if the RTMP stream is healthy using ffprobe.
        Returns True if healthy, False if unhealthy.
        Skips checks if health checking is disabled.
        """
        # Skip health checks if disabled (e.g., when no stream is active)
        with self.lock:
            if not self.enabled:
                return True  # Return healthy when disabled to avoid false alarms
            
            if self.is_checking:
                # Skip without logging to avoid spam
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
                timeout=3  
            )
            
            # If ffprobe succeeds and returns stream info, check for video stream
            if result.returncode == 0 and result.stdout.strip():
                # Check if there's at least one video stream
                output_lines = result.stdout.strip().split('\n')
                has_video = any('video' in line for line in output_lines)
                is_healthy = has_video
                # Only log debug if unhealthy to reduce spam
                if not has_video:
                    logger.debug(f"Stream {self.stream_url} ffprobe: no video stream found")
            else:
                is_healthy = False
                # Only log on first failure or actual errors
                logger.debug(f"Stream {self.stream_url} ffprobe failed: returncode={result.returncode}")
            
            with self.lock:
                current_time = time.time()
                self.last_check_time = current_time
                
                if is_healthy:
                    # Stream is healthy, reset failure tracking
                    # Only log recovery if we were previously unhealthy
                    if not self.is_healthy:
                        logger.info(f"Stream {self.stream_url} recovered and is now healthy")
                    self.is_healthy = True
                    self.first_failure_time = None
                else:
                    # Stream is unhealthy - only log when first detected
                    if self.is_healthy:
                        # First failure detected
                        logger.warning(f"Stream {self.stream_url} health check failed. Starting failure timer.")
                        self.first_failure_time = current_time
                        self.is_healthy = False
                    # Continued failure - no log to avoid spam
                
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
        Returns False if health checking is disabled.
        """
        with self.lock:
            if not self.enabled:
                return False  # Never consider unhealthy when disabled
            
            if self.is_healthy or self.first_failure_time is None:
                return False
            
            current_time = time.time()
            unhealthy_duration = current_time - self.first_failure_time
            
            return unhealthy_duration >= self.unhealthy_threshold_seconds
    
    def get_unhealthy_duration(self) -> float:
        """Get how long the stream has been unhealthy in seconds. Returns 0 if disabled."""
        with self.lock:
            if not self.enabled or self.is_healthy or self.first_failure_time is None:
                return 0.0
            
            current_time = time.time()
            return current_time - self.first_failure_time
    
    def update_stream_url(self, new_stream_url: str):
        """Update the stream URL to monitor, enable health checking, and reset state."""
        with self.lock:
            if self.stream_url != new_stream_url:
                logger.info(f"Health checker now monitoring: {new_stream_url}")
                self.stream_url = new_stream_url
                # Reset state when changing streams
                self.is_healthy = True
                self.first_failure_time = None
                self.last_check_time = None
                self.is_checking = False
                # Enable health checking when a stream URL is set
                self.enabled = True
    
    def is_check_in_progress(self) -> bool:
        """Check if a health check is currently in progress (thread-safe)."""
        with self.lock:
            return self.is_checking
    
    def disable(self):
        """Disable health checking (e.g., when queue is empty)."""
        with self.lock:
            if self.enabled:
                logger.info("Health checker disabled (no active stream)")
                self.enabled = False
                self.is_healthy = True
                self.first_failure_time = None
                self.last_check_time = None
                self.is_checking = False
    
    def reset(self):
        """Reset the health checker state without changing the stream URL or enabled status."""
        with self.lock:
            self.is_healthy = True
            self.first_failure_time = None
            self.last_check_time = None
            self.is_checking = False  # Reset checking flag
            # No log to reduce noise - reset happens frequently during stream switches 