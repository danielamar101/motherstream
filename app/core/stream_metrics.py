"""
Stream Health Metrics Collection System

Provides deep visibility into GStreamer source performance, OBS rendering,
and network conditions to diagnose playback issues.
"""

import time
import csv
import os
import logging
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class StreamHealthSnapshot:
    """Single point-in-time snapshot of stream health metrics."""
    
    # Timestamp
    timestamp: float
    timestamp_str: str
    
    # Source identification
    source_name: str
    rtmp_url: Optional[str]
    
    # OBS Media State
    media_state: Optional[str]  # OBS_MEDIA_STATE_PLAYING, BUFFERING, etc.
    media_duration: Optional[int]  # Total duration in ms
    media_time: Optional[int]  # Current position in ms
    
    # Visibility
    is_visible: bool
    scene_name: str
    
    # Performance metrics
    obs_fps: Optional[float]  # OBS rendering FPS
    dropped_frames: Optional[int]  # Frames dropped by OBS
    
    # Network/Buffer health (from OBS if available)
    buffer_level: Optional[float]  # Percentage
    
    # GStreamer Pipeline Analysis
    gstreamer_state: Optional[str]  # Interpreted pipeline state
    pipeline_healthy: bool  # Overall pipeline health
    pipeline_warnings: List[str]  # Pipeline-specific warnings
    frame_drop_rate: Optional[float]  # Frames/second being dropped
    
    # Computed health indicators
    health_score: float  # 0-100, computed from various metrics
    issues: List[str]  # List of detected issues
    
    # Additional context
    poll_count: int  # Which poll this is
    
    # Enhanced visibility tracking (integrated from obs-stream-switch-monitor.py)
    # These have defaults so must come after non-default fields
    visibility_problematic: bool = False  # True if visible while not PLAYING
    visibility_issue_type: Optional[str] = None  # e.g., "VISIBLE_WHILE_BUFFERING"


class StreamHealthMonitor:
    """
    Monitors stream health in real-time and logs metrics.
    
    Collects detailed metrics about GStreamer sources to diagnose
    playback smoothness issues and other problems.
    
    Now uses hour-based CSV files that aggregate all streams.
    """
    
    # Class-level shared file handles (for hour-based aggregation)
    _shared_csv_file: Optional[str] = None
    _shared_csv_writer = None
    _shared_csv_file_handle = None
    _shared_current_hour: Optional[str] = None
    _file_lock = threading.Lock()  # Thread-safe file access
    
    def __init__(self, metrics_dir: str = "/app/logs/stream-metrics"):
        self.metrics_dir = metrics_dir
        os.makedirs(metrics_dir, exist_ok=True)
        
        # Current monitoring session
        self.current_source: Optional[str] = None
        self.current_rtmp_url: Optional[str] = None
        self.monitoring_active = False
        self.poll_count = 0
        
        # Metrics history (keep last 500 snapshots in memory for hourly reports)
        self.snapshot_history: deque = deque(maxlen=500)
        
        # GStreamer pipeline tracking (per-stream)
        self.last_dropped_frames = 0
        self.last_dropped_frames_time = 0
        
        # Choppiness detection tracking (per-stream)
        self.last_media_time = None
        self.media_time_history = deque(maxlen=10)  # Track last 10 media time readings
        self.fps_history = deque(maxlen=10)  # Track last 10 FPS readings
        self.stall_count = 0  # Count of detected stalls
        
        # Monitoring thread
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Configuration
        self.poll_interval = 1.0  # Check every second
        
        # Reference to OBS manager (will be set externally)
        self.obs_manager = None
        
        # Track last logged status to avoid log spam (per-stream)
        self.last_health_status = None  # Track last health score category
        self.last_pipeline_status = None  # Track last pipeline health status
        
        # Hourly report generation
        self.last_report_hour: Optional[str] = None
        
    def start_monitoring(self, source_name: str, rtmp_url: str, scene_name: str = "MOTHERSTREAM"):
        """Start monitoring a specific source."""
        if self.monitoring_active:
            logger.warning(f"Already monitoring {self.current_source}, stopping that first")
            self.stop_monitoring()
        
        self.current_source = source_name
        self.current_rtmp_url = rtmp_url
        self.scene_name = scene_name
        self.monitoring_active = True
        self.poll_count = 0
        self.stop_event.clear()
        
        # Note: Hourly CSV file will be created lazily when first data is written
        # This prevents empty files when no streams are active
        
        # Reset GStreamer tracking (per-stream)
        self.last_dropped_frames = 0
        self.last_dropped_frames_time = 0
        
        # Reset choppiness detection tracking (per-stream)
        self.last_media_time = None
        self.media_time_history.clear()
        self.fps_history.clear()
        self.stall_count = 0
        
        # Reset status tracking to avoid log spam (per-stream)
        self.last_health_status = None
        self.last_pipeline_status = None
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name=f"StreamHealthMonitor-{source_name}"
        )
        self.monitor_thread.start()
        
        logger.info(f"Started stream health monitoring for '{source_name}' (hourly CSV will be created on first data)")
        
    def stop_monitoring(self):
        """Stop current monitoring session."""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        self.stop_event.set()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        # Note: We don't close the shared CSV file here - it stays open for other streams
        # Hourly reports are generated automatically via _check_and_rotate_hourly_file()
        
        logger.info(f"Stopped stream health monitoring for '{self.current_source}'")
        self.current_source = None
    
    def _get_current_hour_string(self) -> str:
        """Get current hour as a string for file naming (e.g., '20251113-03')."""
        return datetime.now().strftime("%Y%m%d-%H")
    
    def _ensure_hourly_csv_file(self):
        """
        Ensure the hourly CSV file exists and is open.
        Creates a new file if needed, or reuses existing file for the current hour.
        Thread-safe.
        """
        current_hour = self._get_current_hour_string()
        
        with StreamHealthMonitor._file_lock:
            # Check if we need to create/rotate to a new file
            if (StreamHealthMonitor._shared_csv_file is None or 
                StreamHealthMonitor._shared_current_hour != current_hour):
                
                # Close previous file if open
                if StreamHealthMonitor._shared_csv_file_handle:
                    logger.info(f"Closing previous hourly CSV file: {StreamHealthMonitor._shared_csv_file}")
                    StreamHealthMonitor._shared_csv_file_handle.close()
                
                # Create new hourly file
                StreamHealthMonitor._shared_csv_file = os.path.join(
                    self.metrics_dir,
                    f"stream-health-{current_hour}0000.csv"
                )
                
                # Open in append mode (in case file already exists from previous run)
                file_exists = os.path.exists(StreamHealthMonitor._shared_csv_file)
                StreamHealthMonitor._shared_csv_file_handle = open(
                    StreamHealthMonitor._shared_csv_file, 'a', newline=''
                )
                
                StreamHealthMonitor._shared_csv_writer = csv.DictWriter(
                    StreamHealthMonitor._shared_csv_file_handle,
                    fieldnames=[
                        'timestamp', 'timestamp_str', 'source_name', 'rtmp_url',
                        'media_state', 'media_duration', 'media_time',
                        'is_visible', 'scene_name', 'obs_fps', 'dropped_frames',
                        'buffer_level', 'gstreamer_state', 'pipeline_healthy',
                        'pipeline_warnings', 'frame_drop_rate', 'health_score', 
                        'issues', 'poll_count',
                        'visibility_problematic', 'visibility_issue_type'
                    ]
                )
                
                # Write header only if file is new
                if not file_exists:
                    StreamHealthMonitor._shared_csv_writer.writeheader()
                
                StreamHealthMonitor._shared_csv_file_handle.flush()
                StreamHealthMonitor._shared_current_hour = current_hour
                
                logger.info(f"{'Created' if not file_exists else 'Opened'} hourly CSV file: {StreamHealthMonitor._shared_csv_file}")
    
    def _check_and_rotate_hourly_file(self):
        """
        Check if we've entered a new hour and rotate files if needed.
        Also generates report for the previous hour.
        Thread-safe.
        
        Note: Does NOT create a new file immediately - new file is created
        only when there's actual data to write (prevents empty files).
        """
        current_hour = self._get_current_hour_string()
        
        with StreamHealthMonitor._file_lock:
            if (StreamHealthMonitor._shared_current_hour and 
                StreamHealthMonitor._shared_current_hour != current_hour):
                
                # We've entered a new hour! Close previous file and generate report
                previous_csv = StreamHealthMonitor._shared_csv_file
                logger.info(f"Hour changed: {StreamHealthMonitor._shared_current_hour} -> {current_hour}")
                
                # Close the previous file
                if StreamHealthMonitor._shared_csv_file_handle:
                    StreamHealthMonitor._shared_csv_file_handle.close()
                    logger.info(f"Closed previous hourly CSV file: {StreamHealthMonitor._shared_csv_file}")
                
                # Generate hourly report for previous file
                if previous_csv and os.path.exists(previous_csv):
                    self._generate_hourly_report(previous_csv)
                
                # Reset file handles - new file will be created when next data is written
                StreamHealthMonitor._shared_csv_file = None
                StreamHealthMonitor._shared_csv_writer = None
                StreamHealthMonitor._shared_csv_file_handle = None
                StreamHealthMonitor._shared_current_hour = None
                
                logger.info("File handles reset - new file will be created when streams are active")
        
    def _monitoring_loop(self):
        """Background thread that collects metrics at regular intervals."""
        logger.info(f"Stream health monitoring loop started (interval: {self.poll_interval}s)")
        
        while not self.stop_event.is_set():
            try:
                # Check if we need to rotate to a new hourly file
                self._check_and_rotate_hourly_file()
                
                snapshot = self._collect_snapshot()
                if snapshot:
                    self._record_snapshot(snapshot)
                
            except Exception as e:
                logger.error(f"Error collecting stream health snapshot: {e}", exc_info=True)
            
            # Sleep for poll interval
            self.stop_event.wait(self.poll_interval)
        
        logger.info("Stream health monitoring loop stopped")
    
    def _collect_snapshot(self) -> Optional[StreamHealthSnapshot]:
        """Collect current stream health metrics."""
        if not self.obs_manager or not self.current_source:
            return None
        
        self.poll_count += 1
        timestamp = time.time()
        timestamp_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        try:
            # Get OBS media input status
            media_status = self.obs_manager.get_media_input_status(self.current_source)
            
            media_state = None
            media_duration = None
            media_time = None
            
            if media_status:
                media_state = media_status.get('mediaState')
                media_duration = media_status.get('mediaDuration')
                # GStreamer sources use 'mediaCursor' instead of 'mediaTime'
                media_time = media_status.get('mediaTime') or media_status.get('mediaCursor')
            
            # Get visibility
            is_visible = False
            try:
                is_visible = self.obs_manager.is_source_visible(self.current_source, self.scene_name)
            except Exception as e:
                logger.debug(f"Could not check visibility: {e}")
            
            # Detect problematic visibility (integrated from obs-stream-switch-monitor.py)
            # Problem: Source is visible but media is not PLAYING (causes frozen frames!)
            visibility_problematic = False
            visibility_issue_type = None
            
            if is_visible and media_state:
                if media_state == "OBS_MEDIA_STATE_BUFFERING":
                    visibility_problematic = True
                    visibility_issue_type = "VISIBLE_WHILE_BUFFERING"
                elif media_state == "OBS_MEDIA_STATE_STOPPED":
                    visibility_problematic = True
                    visibility_issue_type = "VISIBLE_WHILE_STOPPED"
                elif media_state == "OBS_MEDIA_STATE_PAUSED":
                    visibility_problematic = True
                    visibility_issue_type = "VISIBLE_WHILE_PAUSED"
                elif media_state == "OBS_MEDIA_STATE_ERROR":
                    visibility_problematic = True
                    visibility_issue_type = "VISIBLE_WHILE_ERROR"
                elif media_state not in ["OBS_MEDIA_STATE_PLAYING", None]:
                    visibility_problematic = True
                    visibility_issue_type = f"VISIBLE_WHILE_{media_state.replace('OBS_MEDIA_STATE_', '')}"
            
            # Get OBS stats (if available)
            obs_fps = None
            dropped_frames = None
            try:
                stats = self.obs_manager.get_stats()
                if stats:
                    obs_fps = stats.get('activeFps')
                    dropped_frames = stats.get('renderSkippedFrames')
            except Exception:
                pass  # Stats might not be available
            
            # Detect choppiness patterns
            choppiness_indicators = self._detect_choppiness(
                media_time, obs_fps, media_state
            )
            
            # Analyze GStreamer pipeline
            gstreamer_analysis = self._analyze_gstreamer_pipeline(
                media_state, obs_fps, dropped_frames, timestamp
            )
            
            # Add choppiness indicators to pipeline warnings
            gstreamer_analysis['warnings'].extend(choppiness_indicators)
            if choppiness_indicators:
                gstreamer_analysis['healthy'] = False
            
            # Calculate health score and detect issues
            health_score, issues = self._calculate_health(
                media_state, is_visible, obs_fps, dropped_frames, gstreamer_analysis, choppiness_indicators,
                visibility_problematic, visibility_issue_type
            )
            
            snapshot = StreamHealthSnapshot(
                timestamp=timestamp,
                timestamp_str=timestamp_str,
                source_name=self.current_source,
                rtmp_url=self.current_rtmp_url,
                media_state=media_state,
                media_duration=media_duration,
                media_time=media_time,
                is_visible=is_visible,
                scene_name=self.scene_name,
                obs_fps=obs_fps,
                dropped_frames=dropped_frames,
                buffer_level=None,  # Not directly available from OBS WebSocket
                gstreamer_state=gstreamer_analysis['state'],
                pipeline_healthy=gstreamer_analysis['healthy'],
                pipeline_warnings=gstreamer_analysis['warnings'],
                frame_drop_rate=gstreamer_analysis['frame_drop_rate'],
                health_score=health_score,
                issues=issues,
                poll_count=self.poll_count,
                visibility_problematic=visibility_problematic,
                visibility_issue_type=visibility_issue_type
            )
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error collecting snapshot: {e}", exc_info=True)
            return None
    
    def _detect_choppiness(
        self,
        media_time: Optional[int],
        obs_fps: Optional[float],
        media_state: Optional[str]
    ) -> List[str]:
        """
        Detect various types of playback choppiness.
        
        Returns: List of choppiness indicators
        """
        choppiness_indicators = []
        
        # Track FPS variance
        if obs_fps is not None:
            self.fps_history.append(obs_fps)
            
            if len(self.fps_history) >= 5:
                fps_values = list(self.fps_history)
                fps_variance = max(fps_values) - min(fps_values)
                
                # High FPS variance indicates choppy playback
                if fps_variance > 5:
                    choppiness_indicators.append(f"FPS_VARIANCE_{fps_variance:.1f}")
                
                # Check for FPS drops (even if average is okay)
                recent_fps = fps_values[-3:]
                if any(fps < 24 for fps in recent_fps):
                    choppiness_indicators.append("FPS_DROPS_DETECTED")
        
        # Track media time progression (detects stalls/freezes)
        if media_time is not None and media_state == "OBS_MEDIA_STATE_PLAYING":
            self.media_time_history.append(media_time)
            
            if len(self.media_time_history) >= 3:
                # Check if media time stopped progressing (stall)
                recent_times = list(self.media_time_history)[-3:]
                if recent_times[0] == recent_times[1] == recent_times[2]:
                    self.stall_count += 1
                    choppiness_indicators.append("PLAYBACK_STALLED")
                else:
                    self.stall_count = 0
                
                # Check for timestamp jumps (with YouTube-style buffers, small jumps are absorbed)
                if len(self.media_time_history) >= 2:
                    time_delta = self.media_time_history[-1] - self.media_time_history[-2]
                    expected_delta = self.poll_interval * 1000  # Convert to ms
                    
                    # With 30+ second buffers, only flag LARGE jumps (>3 seconds)
                    # Small variations are absorbed by the massive buffer
                    if abs(time_delta - expected_delta) > 3000:  # >3 second jump
                        choppiness_indicators.append(f"TIMESTAMP_JUMP_{time_delta}ms")
        
        return choppiness_indicators
    
    def _analyze_gstreamer_pipeline(
        self,
        media_state: Optional[str],
        obs_fps: Optional[float],
        dropped_frames: Optional[int],
        current_time: float
    ) -> Dict[str, Any]:
        """
        Analyze GStreamer pipeline health based on observable metrics.
        
        Returns: {
            'state': str,
            'healthy': bool,
            'warnings': List[str],
            'frame_drop_rate': Optional[float]
        }
        """
        warnings = []
        healthy = True
        frame_drop_rate = None
        
        # Map OBS media state to GStreamer pipeline state
        if media_state == "OBS_MEDIA_STATE_PLAYING":
            gst_state = "PLAYING"
        elif media_state == "OBS_MEDIA_STATE_BUFFERING":
            gst_state = "BUFFERING"
            warnings.append("Pipeline buffering - network or decode issue")
            healthy = False
        elif media_state == "OBS_MEDIA_STATE_STOPPED":
            gst_state = "STOPPED"
            warnings.append("Pipeline stopped - stream disconnected")
            healthy = False
        elif media_state == "OBS_MEDIA_STATE_PAUSED":
            gst_state = "PAUSED"
            warnings.append("Pipeline paused")
        elif media_state == "OBS_MEDIA_STATE_ERROR":
            gst_state = "ERROR"
            warnings.append("Pipeline error - critical failure")
            healthy = False
        else:
            gst_state = "UNKNOWN"
            warnings.append("Pipeline state unknown")
        
        # Calculate frame drop rate
        if dropped_frames is not None and dropped_frames > 0:
            if self.last_dropped_frames > 0 and self.last_dropped_frames_time > 0:
                time_delta = current_time - self.last_dropped_frames_time
                frame_delta = dropped_frames - self.last_dropped_frames
                if time_delta > 0:
                    frame_drop_rate = frame_delta / time_delta
                    
                    if frame_drop_rate > 5:
                        warnings.append(f"High frame drop rate: {frame_drop_rate:.1f} fps")
                        healthy = False
                    elif frame_drop_rate > 1:
                        warnings.append(f"Elevated frame drop rate: {frame_drop_rate:.1f} fps")
            
            self.last_dropped_frames = dropped_frames
            self.last_dropped_frames_time = current_time
        
        # Check for pipeline stalls (FPS but wrong state)
        if obs_fps and obs_fps < 15 and gst_state == "PLAYING":
            warnings.append("Pipeline stalled - playing but very low FPS")
            healthy = False
        
        # Check for decode issues (low FPS with PLAYING state)
        if obs_fps and 15 <= obs_fps < 24 and gst_state == "PLAYING":
            warnings.append("Possible decode issues - FPS below target")
        
        return {
            'state': gst_state,
            'healthy': healthy,
            'warnings': warnings,
            'frame_drop_rate': frame_drop_rate
        }
    
    def _calculate_health(
        self, 
        media_state: Optional[str],
        is_visible: bool,
        obs_fps: Optional[float],
        dropped_frames: Optional[int],
        gstreamer_analysis: Dict[str, Any],
        choppiness_indicators: List[str],
        visibility_problematic: bool = False,
        visibility_issue_type: Optional[str] = None
    ) -> tuple[float, List[str]]:
        """
        Calculate overall health score (0-100) and list issues.
        
        Returns: (health_score, issues_list)
        """
        score = 100.0
        issues = []
        
        # Media state checks
        if media_state == "OBS_MEDIA_STATE_STOPPED":
            score -= 50
            issues.append("SOURCE_STOPPED")
        elif media_state == "OBS_MEDIA_STATE_BUFFERING":
            score -= 30
            issues.append("BUFFERING")
        elif media_state == "OBS_MEDIA_STATE_PAUSED":
            score -= 20
            issues.append("PAUSED")
        elif media_state == "OBS_MEDIA_STATE_ERROR":
            score -= 80
            issues.append("ERROR_STATE")
        elif media_state is None:
            score -= 10
            issues.append("NO_STATE_INFO")
        
        # Visibility checks
        if is_visible and media_state not in ["OBS_MEDIA_STATE_PLAYING", None]:
            score -= 25
            issues.append("VISIBLE_NOT_PLAYING")
        
        # Problematic visibility detection (THIS IS THE FROZEN FRAME ISSUE!)
        # Integrated from obs-stream-switch-monitor.py - detects when source becomes
        # visible before it's ready, which causes frozen/black frames during switches
        if visibility_problematic:
            score -= 40  # Major penalty - this is a critical issue!
            issues.append(visibility_issue_type or "VISIBLE_NOT_READY")
            # Note: This warning is now logged in _record_snapshot only when status changes
        
        # FPS checks
        if obs_fps is not None:
            if obs_fps < 20:
                score -= 30
                issues.append(f"LOW_FPS_{obs_fps:.1f}")
            elif obs_fps < 25:
                score -= 15
                issues.append(f"REDUCED_FPS_{obs_fps:.1f}")
        
        # GStreamer pipeline health
        if not gstreamer_analysis['healthy']:
            score -= 20
            issues.append("PIPELINE_UNHEALTHY")
        
        # Frame drop rate
        if gstreamer_analysis['frame_drop_rate']:
            rate = gstreamer_analysis['frame_drop_rate']
            if rate > 5:
                score -= 25
                issues.append(f"HIGH_FRAME_DROPS_{rate:.1f}fps")
            elif rate > 1:
                score -= 10
                issues.append(f"FRAME_DROPS_{rate:.1f}fps")
        
        # Choppiness indicators (THIS IS WHY YOU SEE CHOPPINESS!)
        for indicator in choppiness_indicators:
            if "FPS_VARIANCE" in indicator:
                score -= 20
                issues.append("CHOPPY_FPS_VARIANCE")
            elif "FPS_DROPS" in indicator:
                score -= 15
                issues.append("CHOPPY_FPS_DROPS")
            elif "PLAYBACK_STALLED" in indicator:
                score -= 30
                issues.append("CHOPPY_STALLED")
            elif "TIMESTAMP_JUMP" in indicator:
                score -= 25
                issues.append("CHOPPY_TIMESTAMP_JUMP")
        
        return max(0.0, score), issues
    
    def _record_snapshot(self, snapshot: StreamHealthSnapshot):
        """Record snapshot to CSV and memory."""
        # Add to history
        self.snapshot_history.append(snapshot)
        
        # Ensure hourly CSV file exists before writing (lazy creation - thread-safe)
        # This prevents empty files when no streams are active
        self._ensure_hourly_csv_file()
        
        # Write to shared hourly CSV (thread-safe)
        with StreamHealthMonitor._file_lock:
            if StreamHealthMonitor._shared_csv_writer:
                row = asdict(snapshot)
                # Convert lists to strings (empty string if no items)
                row['issues'] = '; '.join(snapshot.issues) if snapshot.issues else ''
                row['pipeline_warnings'] = '; '.join(snapshot.pipeline_warnings) if snapshot.pipeline_warnings else ''
                
                # Make numeric None values explicit for better CSV readability
                # This prevents empty fields and makes data analysis easier
                if row['buffer_level'] is None:
                    row['buffer_level'] = ''  # Keep empty - not available from OBS WebSocket
                if row['frame_drop_rate'] is None:
                    row['frame_drop_rate'] = 0.0  # Explicit 0 when not actively dropping frames
                if row['media_duration'] is None:
                    row['media_duration'] = 0
                if row['media_time'] is None:
                    row['media_time'] = 0
                if row['obs_fps'] is None:
                    row['obs_fps'] = 0.0
                if row['dropped_frames'] is None:
                    row['dropped_frames'] = 0
                    
                StreamHealthMonitor._shared_csv_writer.writerow(row)
                StreamHealthMonitor._shared_csv_file_handle.flush()
        
        # Categorize health status for change detection
        if snapshot.health_score >= 90:
            health_status = "excellent"
        elif snapshot.health_score >= 70:
            health_status = "good"
        elif snapshot.health_score >= 50:
            health_status = "degraded"
        else:
            health_status = "poor"
        
        # Only log health issues when status changes or on first poll
        if health_status != self.last_health_status:
            if snapshot.health_score < 70:
                logger.warning(
                    f"Stream health {health_status}: {snapshot.source_name} "
                    f"score={snapshot.health_score:.1f} issues={snapshot.issues}"
                )
            elif self.last_health_status and self.last_health_status in ["degraded", "poor"]:
                # Log when health improves
                logger.info(
                    f"Stream health improved: {snapshot.source_name} "
                    f"score={snapshot.health_score:.1f}"
                )
            self.last_health_status = health_status
        
        # Only log pipeline warnings when they change or appear for the first time
        pipeline_status = f"{snapshot.pipeline_healthy}:{','.join(sorted(snapshot.pipeline_warnings))}"
        if pipeline_status != self.last_pipeline_status:
            if snapshot.pipeline_warnings and not snapshot.pipeline_healthy:
                logger.warning(
                    f"GStreamer pipeline issues: {snapshot.source_name} "
                    f"state={snapshot.gstreamer_state} warnings={snapshot.pipeline_warnings}"
                )
            elif self.last_pipeline_status and not self.last_pipeline_status.startswith("True"):
                # Log when pipeline recovers
                logger.info(
                    f"GStreamer pipeline recovered: {snapshot.source_name} state={snapshot.gstreamer_state}"
                )
            self.last_pipeline_status = pipeline_status
    
    def _generate_hourly_report(self, csv_file: str):
        """
        Generate a human-readable hourly report for ALL streams in the CSV file.
        Reads the CSV file and aggregates stats across all sources.
        """
        if not csv_file or not os.path.exists(csv_file):
            return
        
        report_file = csv_file.replace('.csv', '-report.txt')
        
        try:
            # Read CSV file and aggregate data across all sources
            rows = []
            with open(csv_file, 'r') as csvf:
                reader = csv.DictReader(csvf)
                rows = list(reader)
            
            if not rows:
                logger.warning(f"No data in CSV file {csv_file}, skipping report generation")
                return
            
            # Extract hour timestamp from filename
            filename = os.path.basename(csv_file)
            hour_str = filename.replace('stream-health-', '').replace('.csv', '')
            
            # Aggregate stats across all sources
            sources = {}  # source_name -> stats
            all_health_scores = []
            all_issues = {}
            all_states = {}
            total_polls = len(rows)
            
            for row in rows:
                source_name = row.get('source_name', 'UNKNOWN')
                
                # Initialize source stats if new
                if source_name not in sources:
                    sources[source_name] = {
                        'polls': 0,
                        'health_scores': [],
                        'issues': {},
                        'states': {}
                    }
                
                # Aggregate per-source
                sources[source_name]['polls'] += 1
                
                try:
                    health_score = float(row.get('health_score', 0))
                    sources[source_name]['health_scores'].append(health_score)
                    all_health_scores.append(health_score)
                except (ValueError, TypeError):
                    pass
                
                # Count issues
                issues_str = row.get('issues', '')
                if issues_str:
                    for issue in issues_str.split('; '):
                        if issue:
                            sources[source_name]['issues'][issue] = sources[source_name]['issues'].get(issue, 0) + 1
                            all_issues[issue] = all_issues.get(issue, 0) + 1
                
                # Track states
                state = row.get('media_state', 'UNKNOWN')
                sources[source_name]['states'][state] = sources[source_name]['states'].get(state, 0) + 1
                all_states[state] = all_states.get(state, 0) + 1
            
            # Write report
            with open(report_file, 'w') as f:
                f.write("=" * 70 + "\n")
                f.write("HOURLY STREAM HEALTH MONITORING REPORT\n")
                f.write("=" * 70 + "\n\n")
                
                f.write(f"Time Period: {hour_str}\n")
                f.write(f"Data File: {os.path.basename(csv_file)}\n")
                f.write(f"Total Streams: {len(sources)}\n")
                f.write(f"Total Data Points: {total_polls}\n")
                f.write("\n")
                
                # Overall health summary
                if all_health_scores:
                    avg_health = sum(all_health_scores) / len(all_health_scores)
                    min_health = min(all_health_scores)
                    max_health = max(all_health_scores)
                    
                    f.write("OVERALL HEALTH SUMMARY:\n")
                    f.write("-" * 70 + "\n")
                    f.write(f"  Average Health Score: {avg_health:.1f}/100\n")
                    f.write(f"  Min Health Score: {min_health:.1f}/100\n")
                    f.write(f"  Max Health Score: {max_health:.1f}/100\n")
                    f.write("\n")
                
                # Per-stream breakdown
                f.write("PER-STREAM BREAKDOWN:\n")
                f.write("-" * 70 + "\n")
                for source_name, stats in sorted(sources.items()):
                    if stats['health_scores']:
                        avg = sum(stats['health_scores']) / len(stats['health_scores'])
                        f.write(f"\n  {source_name}:\n")
                        f.write(f"    Data Points: {stats['polls']}\n")
                        f.write(f"    Avg Health: {avg:.1f}/100\n")
                        
                        if stats['issues']:
                            f.write(f"    Issues: {', '.join(stats['issues'].keys())}\n")
                        else:
                            f.write(f"    Issues: None ✓\n")
                f.write("\n")
                
                # All issues detected
                if all_issues:
                    f.write("ALL ISSUES DETECTED:\n")
                    f.write("-" * 70 + "\n")
                    for issue, count in sorted(all_issues.items(), key=lambda x: -x[1]):
                        percentage = (count / total_polls) * 100
                        f.write(f"  {issue}: {count} times ({percentage:.1f}% of polls)\n")
                    f.write("\n")
                else:
                    f.write("ALL ISSUES DETECTED:\n")
                    f.write("-" * 70 + "\n")
                    f.write("  No issues detected! ✓\n\n")
                
                # State distribution
                f.write("MEDIA STATE DISTRIBUTION:\n")
                f.write("-" * 70 + "\n")
                for state, count in sorted(all_states.items(), key=lambda x: -x[1]):
                    percentage = (count / total_polls) * 100
                    f.write(f"  {state}: {count} polls ({percentage:.1f}%)\n")
                f.write("\n")
                
                # Recommendations
                f.write("RECOMMENDATIONS:\n")
                f.write("-" * 70 + "\n")
                
                if all_health_scores:
                    avg_health = sum(all_health_scores) / len(all_health_scores)
                    if avg_health >= 90:
                        f.write("  ✓ Stream health is excellent! No action needed.\n")
                    elif avg_health >= 70:
                        f.write("  ⚠ Stream health is acceptable but could be improved.\n")
                        f.write("  → Check for intermittent network issues\n")
                        f.write("  → Monitor during peak hours\n")
                    else:
                        f.write("  ✗ Stream health is poor. Immediate action recommended!\n")
                        
                        if "BUFFERING" in all_issues:
                            f.write("  → High buffering detected - check network bandwidth\n")
                            f.write("  → Consider reducing stream bitrate\n")
                        
                        if any("LOW_FPS" in issue for issue in all_issues.keys()):
                            f.write("  → Low FPS detected - check system resources\n")
                            f.write("  → Reduce OBS encoding load\n")
                        
                        if "VISIBLE_NOT_PLAYING" in all_issues or "VISIBLE_WHILE_BUFFERING" in all_issues:
                            f.write("  → Source visible before ready - increase buffer time\n")
                
                f.write("\n")
                f.write("=" * 70 + "\n")
                f.write("End of Report\n")
                f.write("=" * 70 + "\n")
            
            logger.info(f"Generated hourly health report: {report_file}")
            
        except Exception as e:
            logger.error(f"Failed to generate hourly report: {e}", exc_info=True)
    
    def get_current_health(self) -> Optional[Dict[str, Any]]:
        """Get the most recent health snapshot as a dictionary."""
        if not self.snapshot_history:
            return None
        
        latest = self.snapshot_history[-1]
        return asdict(latest)
    
    def get_health_history(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get the last N health snapshots."""
        history_list = list(self.snapshot_history)
        recent = history_list[-count:] if len(history_list) > count else history_list
        return [asdict(s) for s in recent]
    
    @classmethod
    def generate_report_for_csv(cls, csv_file: str):
        """
        Convenience method to manually generate a report for any CSV file.
        Useful for regenerating reports or creating reports for existing files.
        """
        instance = cls()
        instance._generate_hourly_report(csv_file)


# Global instance
stream_health_monitor = StreamHealthMonitor()

