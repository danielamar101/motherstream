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


class StreamHealthMonitor:
    """
    Monitors stream health in real-time and logs metrics.
    
    Collects detailed metrics about GStreamer sources to diagnose
    playback smoothness issues and other problems.
    """
    
    def __init__(self, metrics_dir: str = "/app/logs/stream-metrics"):
        self.metrics_dir = metrics_dir
        os.makedirs(metrics_dir, exist_ok=True)
        
        # Current monitoring session
        self.current_source: Optional[str] = None
        self.current_rtmp_url: Optional[str] = None
        self.monitoring_active = False
        self.poll_count = 0
        
        # Metrics history (keep last 100 snapshots in memory)
        self.snapshot_history: deque = deque(maxlen=100)
        
        # CSV file for current session
        self.current_csv_file: Optional[str] = None
        self.csv_writer = None
        self.csv_file_handle = None
        
        # GStreamer pipeline tracking
        self.last_dropped_frames = 0
        self.last_dropped_frames_time = 0
        
        # Choppiness detection tracking
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
        
        # Create new CSV file for this session
        timestamp_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_source_name = source_name.replace("/", "-").replace(" ", "_")
        self.current_csv_file = os.path.join(
            self.metrics_dir, 
            f"stream-health-{safe_source_name}-{timestamp_str}.csv"
        )
        
        # Open CSV file
        self.csv_file_handle = open(self.current_csv_file, 'w', newline='')
        self.csv_writer = csv.DictWriter(
            self.csv_file_handle,
            fieldnames=[
                'timestamp', 'timestamp_str', 'source_name', 'rtmp_url',
                'media_state', 'media_duration', 'media_time',
                'is_visible', 'scene_name', 'obs_fps', 'dropped_frames',
                'buffer_level', 'gstreamer_state', 'pipeline_healthy',
                'pipeline_warnings', 'frame_drop_rate', 'health_score', 
                'issues', 'poll_count'
            ]
        )
        self.csv_writer.writeheader()
        self.csv_file_handle.flush()
        
        # Reset GStreamer tracking
        self.last_dropped_frames = 0
        self.last_dropped_frames_time = 0
        
        # Reset choppiness detection tracking
        self.last_media_time = None
        self.media_time_history.clear()
        self.fps_history.clear()
        self.stall_count = 0
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name=f"StreamHealthMonitor-{source_name}"
        )
        self.monitor_thread.start()
        
        logger.info(f"Started stream health monitoring for '{source_name}' -> {self.current_csv_file}")
        
    def stop_monitoring(self):
        """Stop current monitoring session."""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        self.stop_event.set()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        if self.csv_file_handle:
            self.csv_file_handle.close()
            self.csv_file_handle = None
            self.csv_writer = None
        
        # Generate summary report
        if self.current_csv_file:
            self._generate_summary_report()
        
        logger.info(f"Stopped stream health monitoring for '{self.current_source}'")
        self.current_source = None
        
    def _monitoring_loop(self):
        """Background thread that collects metrics at regular intervals."""
        logger.info(f"Stream health monitoring loop started (interval: {self.poll_interval}s)")
        
        while not self.stop_event.is_set():
            try:
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
                media_state, is_visible, obs_fps, dropped_frames, gstreamer_analysis, choppiness_indicators
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
                poll_count=self.poll_count
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
        choppiness_indicators: List[str]
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
        
        # Write to CSV
        if self.csv_writer:
            row = asdict(snapshot)
            row['issues'] = '; '.join(snapshot.issues)  # Convert list to string
            row['pipeline_warnings'] = '; '.join(snapshot.pipeline_warnings)  # Convert list to string
            self.csv_writer.writerow(row)
            self.csv_file_handle.flush()
        
        # Log significant issues
        if snapshot.health_score < 70:
            logger.warning(
                f"Stream health degraded: {snapshot.source_name} "
                f"score={snapshot.health_score:.1f} issues={snapshot.issues}"
            )
        
        # Log GStreamer warnings
        if snapshot.pipeline_warnings and not snapshot.pipeline_healthy:
            logger.warning(
                f"GStreamer pipeline issues: {snapshot.source_name} "
                f"state={snapshot.gstreamer_state} warnings={snapshot.pipeline_warnings}"
            )
    
    def _generate_summary_report(self):
        """Generate a human-readable summary report."""
        if not self.current_csv_file:
            return
        
        report_file = self.current_csv_file.replace('.csv', '-report.txt')
        
        try:
            with open(report_file, 'w') as f:
                f.write("=" * 70 + "\n")
                f.write("STREAM HEALTH MONITORING REPORT\n")
                f.write("=" * 70 + "\n\n")
                
                f.write(f"Source: {self.current_source}\n")
                f.write(f"RTMP URL: {self.current_rtmp_url}\n")
                f.write(f"Total Polls: {self.poll_count}\n")
                f.write(f"Duration: {self.poll_count * self.poll_interval:.1f} seconds\n")
                f.write(f"Data File: {os.path.basename(self.current_csv_file)}\n")
                f.write("\n")
                
                # Analyze history
                if self.snapshot_history:
                    health_scores = [s.health_score for s in self.snapshot_history]
                    avg_health = sum(health_scores) / len(health_scores)
                    min_health = min(health_scores)
                    max_health = max(health_scores)
                    
                    f.write("HEALTH SUMMARY:\n")
                    f.write("-" * 70 + "\n")
                    f.write(f"  Average Health Score: {avg_health:.1f}/100\n")
                    f.write(f"  Min Health Score: {min_health:.1f}/100\n")
                    f.write(f"  Max Health Score: {max_health:.1f}/100\n")
                    f.write("\n")
                    
                    # Count issues
                    all_issues = {}
                    for snapshot in self.snapshot_history:
                        for issue in snapshot.issues:
                            all_issues[issue] = all_issues.get(issue, 0) + 1
                    
                    if all_issues:
                        f.write("ISSUES DETECTED:\n")
                        f.write("-" * 70 + "\n")
                        for issue, count in sorted(all_issues.items(), key=lambda x: -x[1]):
                            percentage = (count / len(self.snapshot_history)) * 100
                            f.write(f"  {issue}: {count} times ({percentage:.1f}% of polls)\n")
                        f.write("\n")
                    else:
                        f.write("No issues detected! ✓\n\n")
                    
                    # State distribution
                    state_counts = {}
                    for snapshot in self.snapshot_history:
                        state = snapshot.media_state or "UNKNOWN"
                        state_counts[state] = state_counts.get(state, 0) + 1
                    
                    f.write("MEDIA STATE DISTRIBUTION:\n")
                    f.write("-" * 70 + "\n")
                    for state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
                        percentage = (count / len(self.snapshot_history)) * 100
                        f.write(f"  {state}: {count} polls ({percentage:.1f}%)\n")
                    f.write("\n")
                    
                    # Recommendations
                    f.write("RECOMMENDATIONS:\n")
                    f.write("-" * 70 + "\n")
                    
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
                        
                        if "LOW_FPS" in str(all_issues):
                            f.write("  → Low FPS detected - check system resources\n")
                            f.write("  → Reduce OBS encoding load\n")
                        
                        if "VISIBLE_NOT_PLAYING" in all_issues:
                            f.write("  → Source visible before ready - increase buffer time\n")
                    
                    f.write("\n")
                
                f.write("=" * 70 + "\n")
                f.write("End of Report\n")
                f.write("=" * 70 + "\n")
            
            logger.info(f"Generated health report: {report_file}")
            
        except Exception as e:
            logger.error(f"Failed to generate summary report: {e}", exc_info=True)
    
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


# Global instance
stream_health_monitor = StreamHealthMonitor()

