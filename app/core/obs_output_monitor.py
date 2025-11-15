"""
OBS Output Stream Performance Monitor

Monitors the OUTGOING stream from OBS to detect quality issues under high load.
This is different from input stream monitoring - it checks if OBS can keep up
with encoding/streaming all the concurrent streams it's receiving.

Critical for detecting: 
- Encoding lag (CPU can't keep up)
- Skipped frames (encoder dropping frames)
- Bitrate drops (network saturation)
- Rendering issues
"""

import time
import logging
import threading
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import deque
import csv
import os

logger = logging.getLogger(__name__)


@dataclass
class OBSOutputSnapshot:
    """Snapshot of OBS output performance at a point in time"""
    timestamp: float
    timestamp_str: str
    
    # Rendering performance
    active_fps: Optional[float]  # Actual rendering FPS
    average_frame_time: Optional[float]  # ms per frame
    render_skipped_frames: Optional[int]  # Cumulative skipped render frames
    render_total_frames: Optional[int]  # Total frames rendered
    
    # Encoding performance  
    output_skipped_frames: Optional[int]  # Cumulative skipped encoding frames
    output_total_frames: Optional[int]  # Total frames encoded
    
    # Output bandwidth
    output_bytes: Optional[int]  # Total bytes sent
    output_duration: Optional[int]  # Total streaming time (ms)
    
    # CPU usage
    cpu_usage: Optional[float]  # OBS CPU usage %
    
    # Memory
    memory_usage: Optional[float]  # OBS memory usage MB
    
    # Streaming status
    is_streaming: bool
    
    # Computed metrics
    render_skip_rate: Optional[float]  # Frames/sec being skipped in rendering
    encoding_skip_rate: Optional[float]  # Frames/sec being skipped in encoding
    current_bitrate_mbps: Optional[float]  # Current output bitrate
    
    # Health indicators
    health_score: float  # 0-100
    issues: List[str]  # Detected issues
    is_degraded: bool  # True if performance is degraded


class OBSOutputMonitor:
    """
    Monitors OBS output stream performance to detect issues under high load.
    
    Unlike input stream monitoring, this focuses on whether OBS itself can
    keep up with encoding and streaming all the sources it's processing.
    """
    
    def __init__(self, obs_manager, log_dir: str = "./docker-volume-mounts/logs/obs-output",
                 poll_interval: float = 2.0, history_size: int = 60):
        """
        Args:
            obs_manager: OBSSocketManager instance
            log_dir: Directory to save logs
            poll_interval: Seconds between polls
            history_size: Number of snapshots to keep in memory
        """
        self.obs_manager = obs_manager
        self.log_dir = log_dir
        self.poll_interval = poll_interval
        self.history_size = history_size
        
        self.snapshots = deque(maxlen=history_size)
        self.is_monitoring = False
        self.monitor_thread = None
        self.lock = threading.Lock()
        
        # Baseline for rate calculations
        self.last_snapshot_time = None
        self.last_render_skipped = 0
        self.last_output_skipped = 0
        self.last_output_bytes = 0
        
        # Degradation thresholds
        self.RENDER_SKIP_RATE_WARNING = 1.0  # fps
        self.RENDER_SKIP_RATE_CRITICAL = 5.0  # fps
        self.ENCODING_SKIP_RATE_WARNING = 1.0  # fps
        self.ENCODING_SKIP_RATE_CRITICAL = 5.0  # fps
        self.FPS_WARNING = 28.0  # Below target
        self.FPS_CRITICAL = 25.0
        self.FRAME_TIME_WARNING = 40.0  # ms (should be ~33ms for 30fps)
        self.FRAME_TIME_CRITICAL = 50.0  # ms
        
        os.makedirs(log_dir, exist_ok=True)
        
        # CSV file (one per session)
        self.csv_file = None
        self.csv_writer = None
        
    def start_monitoring(self):
        """Start continuous monitoring in background thread"""
        with self.lock:
            if self.is_monitoring:
                logger.warning("OBS output monitoring already running")
                return
            
            self.is_monitoring = True
            
            # Create new CSV file
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            csv_path = os.path.join(self.log_dir, f"obs-output-{timestamp}.csv")
            self.csv_file = open(csv_path, 'w', newline='')
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=[
                'timestamp', 'timestamp_str', 'active_fps', 'average_frame_time',
                'render_skipped_frames', 'render_total_frames', 'output_skipped_frames',
                'output_total_frames', 'output_bytes', 'cpu_usage', 'memory_usage',
                'is_streaming', 'render_skip_rate', 'encoding_skip_rate',
                'current_bitrate_mbps', 'health_score', 'issues', 'is_degraded'
            ])
            self.csv_writer.writeheader()
            
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info(f"OBS output monitoring started, logging to {csv_path}")
    
    def stop_monitoring(self):
        """Stop monitoring and save report"""
        with self.lock:
            if not self.is_monitoring:
                return
            
            self.is_monitoring = False
            
        # Wait for thread to finish
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        
        # Close CSV
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None
        
        # Generate report
        self._generate_report()
        
        logger.info("OBS output monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                snapshot = self._collect_snapshot()
                if snapshot:
                    with self.lock:
                        self.snapshots.append(snapshot)
                    
                    # Log to CSV
                    if self.csv_writer:
                        row = asdict(snapshot)
                        row['issues'] = '; '.join(row['issues'])
                        self.csv_writer.writerow(row)
                        self.csv_file.flush()
                    
                    # Log warnings
                    if snapshot.issues:
                        logger.warning(f"OBS output degraded: {', '.join(snapshot.issues)}")
                
            except Exception as e:
                logger.error(f"Error in OBS output monitor loop: {e}")
            
            time.sleep(self.poll_interval)
    
    def _collect_snapshot(self) -> Optional[OBSOutputSnapshot]:
        """Collect current OBS output stats"""
        try:
            stats = self.obs_manager.get_stats()
            if not stats:
                return None
            
            timestamp = time.time()
            
            # Extract metrics
            active_fps = stats.get('activeFps')
            average_frame_time = stats.get('averageFrameRenderTime')
            render_skipped = stats.get('renderSkippedFrames', 0)
            render_total = stats.get('renderTotalFrames', 0)
            output_skipped = stats.get('outputSkippedFrames', 0)
            output_total = stats.get('outputTotalFrames', 0)
            output_bytes = stats.get('outputBytes', 0)
            output_duration = stats.get('outputDuration', 0)
            cpu_usage = stats.get('cpuUsage')
            memory_usage = stats.get('memoryUsage')
            
            # Check streaming status
            try:
                streaming_status = self.obs_manager.get_output_status()
                is_streaming = streaming_status.get('outputActive', False) if streaming_status else False
            except:
                is_streaming = False
            
            # Calculate rates (skipped frames per second)
            render_skip_rate = None
            encoding_skip_rate = None
            current_bitrate_mbps = None
            
            if self.last_snapshot_time:
                time_delta = timestamp - self.last_snapshot_time
                
                if time_delta > 0:
                    # Render skip rate
                    render_skip_delta = render_skipped - self.last_render_skipped
                    render_skip_rate = render_skip_delta / time_delta
                    
                    # Encoding skip rate
                    encoding_skip_delta = output_skipped - self.last_output_skipped
                    encoding_skip_rate = encoding_skip_delta / time_delta
                    
                    # Current bitrate (Mbps)
                    bytes_delta = output_bytes - self.last_output_bytes
                    current_bitrate_mbps = (bytes_delta * 8) / (time_delta * 1_000_000)
            
            # Update baselines
            self.last_snapshot_time = timestamp
            self.last_render_skipped = render_skipped
            self.last_output_skipped = output_skipped
            self.last_output_bytes = output_bytes
            
            # Analyze health
            health_score, issues, is_degraded = self._analyze_health(
                active_fps, average_frame_time, render_skip_rate,
                encoding_skip_rate, current_bitrate_mbps, is_streaming
            )
            
            return OBSOutputSnapshot(
                timestamp=timestamp,
                timestamp_str=datetime.fromtimestamp(timestamp).isoformat(),
                active_fps=active_fps,
                average_frame_time=average_frame_time,
                render_skipped_frames=render_skipped,
                render_total_frames=render_total,
                output_skipped_frames=output_skipped,
                output_total_frames=output_total,
                output_bytes=output_bytes,
                output_duration=output_duration,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                is_streaming=is_streaming,
                render_skip_rate=render_skip_rate,
                encoding_skip_rate=encoding_skip_rate,
                current_bitrate_mbps=current_bitrate_mbps,
                health_score=health_score,
                issues=issues,
                is_degraded=is_degraded
            )
            
        except Exception as e:
            logger.error(f"Failed to collect OBS output snapshot: {e}")
            return None
    
    def _analyze_health(self, active_fps: Optional[float], 
                       average_frame_time: Optional[float],
                       render_skip_rate: Optional[float],
                       encoding_skip_rate: Optional[float],
                       current_bitrate_mbps: Optional[float],
                       is_streaming: bool) -> tuple[float, List[str], bool]:
        """Analyze OBS output health and return (health_score, issues, is_degraded)"""
        
        health_score = 100.0
        issues = []
        is_degraded = False
        
        # Not streaming is not an issue
        if not is_streaming:
            return 100.0, [], False
        
        # Check FPS
        if active_fps is not None:
            if active_fps < self.FPS_CRITICAL:
                issues.append(f"CRITICAL_LOW_FPS_{active_fps:.1f}")
                health_score -= 40
                is_degraded = True
            elif active_fps < self.FPS_WARNING:
                issues.append(f"LOW_FPS_{active_fps:.1f}")
                health_score -= 20
                is_degraded = True
        
        # Check frame time (rendering speed)
        if average_frame_time is not None:
            if average_frame_time > self.FRAME_TIME_CRITICAL:
                issues.append(f"CRITICAL_SLOW_RENDERING_{average_frame_time:.1f}ms")
                health_score -= 30
                is_degraded = True
            elif average_frame_time > self.FRAME_TIME_WARNING:
                issues.append(f"SLOW_RENDERING_{average_frame_time:.1f}ms")
                health_score -= 15
                is_degraded = True
        
        # Check render skip rate
        if render_skip_rate is not None and render_skip_rate > 0:
            if render_skip_rate > self.RENDER_SKIP_RATE_CRITICAL:
                issues.append(f"CRITICAL_RENDER_SKIPPING_{render_skip_rate:.1f}fps")
                health_score -= 35
                is_degraded = True
            elif render_skip_rate > self.RENDER_SKIP_RATE_WARNING:
                issues.append(f"RENDER_SKIPPING_{render_skip_rate:.1f}fps")
                health_score -= 20
                is_degraded = True
        
        # Check encoding skip rate (MOST IMPORTANT for choppy output!)
        if encoding_skip_rate is not None and encoding_skip_rate > 0:
            if encoding_skip_rate > self.ENCODING_SKIP_RATE_CRITICAL:
                issues.append(f"CRITICAL_ENCODING_SKIPPING_{encoding_skip_rate:.1f}fps")
                health_score -= 40
                is_degraded = True
            elif encoding_skip_rate > self.ENCODING_SKIP_RATE_WARNING:
                issues.append(f"ENCODING_SKIPPING_{encoding_skip_rate:.1f}fps")
                health_score -= 25
                is_degraded = True
        
        # Check bitrate (sudden drops indicate network issues)
        if current_bitrate_mbps is not None:
            # This is tricky - need history to detect drops
            # For now, just log very low bitrate
            if current_bitrate_mbps < 1.0 and is_streaming:
                issues.append(f"LOW_BITRATE_{current_bitrate_mbps:.2f}Mbps")
                health_score -= 15
                is_degraded = True
        
        return max(0, health_score), issues, is_degraded
    
    def _generate_report(self):
        """Generate summary report from collected data"""
        if not self.snapshots:
            return
        
        # Calculate statistics
        total_snapshots = len(self.snapshots)
        degraded_snapshots = sum(1 for s in self.snapshots if s.is_degraded)
        degraded_percent = (degraded_snapshots / total_snapshots) * 100
        
        fps_values = [s.active_fps for s in self.snapshots if s.active_fps is not None]
        avg_fps = sum(fps_values) / len(fps_values) if fps_values else 0
        min_fps = min(fps_values) if fps_values else 0
        
        frame_time_values = [s.average_frame_time for s in self.snapshots if s.average_frame_time is not None]
        avg_frame_time = sum(frame_time_values) / len(frame_time_values) if frame_time_values else 0
        max_frame_time = max(frame_time_values) if frame_time_values else 0
        
        render_skip_rates = [s.render_skip_rate for s in self.snapshots if s.render_skip_rate is not None and s.render_skip_rate > 0]
        max_render_skip = max(render_skip_rates) if render_skip_rates else 0
        
        encoding_skip_rates = [s.encoding_skip_rate for s in self.snapshots if s.encoding_skip_rate is not None and s.encoding_skip_rate > 0]
        max_encoding_skip = max(encoding_skip_rates) if encoding_skip_rates else 0
        
        # Count issue types
        all_issues = []
        for s in self.snapshots:
            all_issues.extend(s.issues)
        
        issue_counts = {}
        for issue in all_issues:
            # Get issue type (before the _number)
            issue_type = issue.split('_')[0] + '_' + issue.split('_')[1] if '_' in issue else issue
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        # Write report
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_path = os.path.join(self.log_dir, f"obs-output-report-{timestamp}.txt")
        
        with open(report_path, 'w') as f:
            f.write("="*80 + "\n")
            f.write("OBS OUTPUT PERFORMANCE REPORT\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Monitoring Duration: {self.snapshots[-1].timestamp - self.snapshots[0].timestamp:.1f} seconds\n")
            f.write(f"Total Snapshots: {total_snapshots}\n")
            f.write(f"Degraded Snapshots: {degraded_snapshots} ({degraded_percent:.1f}%)\n\n")
            
            f.write("PERFORMANCE SUMMARY:\n")
            f.write("-"*40 + "\n")
            f.write(f"Average FPS: {avg_fps:.2f}\n")
            f.write(f"Minimum FPS: {min_fps:.2f}\n")
            f.write(f"Average Frame Time: {avg_frame_time:.2f}ms\n")
            f.write(f"Maximum Frame Time: {max_frame_time:.2f}ms\n")
            f.write(f"Peak Render Skip Rate: {max_render_skip:.2f} fps\n")
            f.write(f"Peak Encoding Skip Rate: {max_encoding_skip:.2f} fps\n\n")
            
            if issue_counts:
                f.write("ISSUES DETECTED:\n")
                f.write("-"*40 + "\n")
                for issue_type, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"{issue_type}: {count} times\n")
                f.write("\n")
            
            f.write("RECOMMENDATIONS:\n")
            f.write("-"*40 + "\n")
            if max_encoding_skip > 5:
                f.write("⚠️  HIGH ENCODING SKIP RATE - CPU cannot keep up with encoding\n")
                f.write("   Solutions:\n")
                f.write("   - Reduce concurrent stream count\n")
                f.write("   - Use faster encoder preset (veryfast, superfast, ultrafast)\n")
                f.write("   - Use hardware encoding (NVENC, QuickSync, etc.)\n")
                f.write("   - Upgrade CPU\n\n")
            
            if max_render_skip > 5:
                f.write("⚠️  HIGH RENDER SKIP RATE - Rendering cannot keep up\n")
                f.write("   Solutions:\n")
                f.write("   - Reduce scene complexity\n")
                f.write("   - Lower output resolution\n")
                f.write("   - Upgrade GPU\n\n")
            
            if min_fps < 25:
                f.write("⚠️  FPS DROPS DETECTED - Output quality degraded\n")
                f.write("   Solutions:\n")
                f.write("   - Check CPU usage\n")
                f.write("   - Reduce concurrent stream count\n")
                f.write("   - Optimize OBS settings\n\n")
            
            if max_frame_time > 50:
                f.write("⚠️  SLOW FRAME RENDERING - Each frame taking too long\n")
                f.write("   Solutions:\n")
                f.write("   - Reduce scene complexity\n")
                f.write("   - Disable expensive filters\n")
                f.write("   - Lower output resolution\n\n")
            
            if degraded_percent < 5:
                f.write("✅ OUTPUT QUALITY EXCELLENT - System handling load well\n")
            elif degraded_percent < 20:
                f.write("⚠️  OUTPUT QUALITY OCCASIONALLY DEGRADED - Near capacity\n")
            else:
                f.write("❌ OUTPUT QUALITY FREQUENTLY DEGRADED - Over capacity\n")
            
            f.write("\n" + "="*80 + "\n")
        
        logger.info(f"OBS output report saved to {report_path}")
    
    def get_current_status(self) -> Optional[Dict]:
        """Get current OBS output status"""
        with self.lock:
            if not self.snapshots:
                return None
            
            latest = self.snapshots[-1]
            return {
                'timestamp': latest.timestamp_str,
                'is_streaming': latest.is_streaming,
                'active_fps': latest.active_fps,
                'render_skip_rate': latest.render_skip_rate,
                'encoding_skip_rate': latest.encoding_skip_rate,
                'health_score': latest.health_score,
                'is_degraded': latest.is_degraded,
                'issues': latest.issues
            }

