"""
Enhanced GStreamer Source Health Checker

Detects GStreamer-specific issues that don't show up in basic OBS status:
- Pipeline underruns (buffer starvation)
- Decoding stalls (media_time not progressing)
- Queue overflow/underflow
- Network issues causing rebuffering
- Frame skipping in decode pipeline

These issues cause choppy playback but may report "PLAYING" state!
"""

import logging
import time
from typing import Optional, Dict, List, Tuple
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GStreamerHealthStatus:
    """Health status of GStreamer source"""
    is_healthy: bool
    health_score: float  # 0-100
    issues: List[str]
    warnings: List[str]
    
    # Detailed metrics
    media_time_progressing: bool
    media_time_stall_duration: float  # seconds
    media_time_jitter: float  # ms variance
    effective_framerate: Optional[float]  # calculated from media_time
    decode_lag_detected: bool
    buffer_underrun_likely: bool
    
    # Historical context
    stall_count_last_minute: int
    health_trend: str  # "improving", "stable", "degrading"


class GStreamerHealthChecker:
    """
    Advanced health checking specifically for GStreamer sources.
    
    Detects issues that OBS media state doesn't catch:
    - Media time not progressing (frozen frames while "PLAYING")
    - Irregular time progression (jitter, jumps)
    - Decode stalls (long gaps between frames)
    - Buffer underruns (insufficient data causing stuttering)
    """
    
    def __init__(self, stall_threshold_ms: int = 500, 
                 jitter_threshold_ms: int = 100):
        """
        Args:
            stall_threshold_ms: Consider stalled if media_time doesn't advance this long
            jitter_threshold_ms: Consider jittery if time jumps exceed this
        """
        self.stall_threshold_ms = stall_threshold_ms
        self.jitter_threshold_ms = jitter_threshold_ms
        
        # Historical tracking
        self.media_time_history = deque(maxlen=60)  # Last 60 samples
        self.last_media_time = None
        self.last_check_timestamp = None
        self.stall_start_time = None
        self.stall_events = deque(maxlen=60)  # Track stalls in last minute
        
        # Metrics
        self.total_stalls = 0
        self.total_jitter_events = 0
        self.consecutive_healthy_checks = 0
        self.consecutive_unhealthy_checks = 0
        
    def check_health(self, media_state: Optional[str], 
                     media_time: Optional[int],
                     obs_fps: Optional[float],
                     is_visible: bool) -> GStreamerHealthStatus:
        """
        Comprehensive health check of GStreamer source.
        
        Args:
            media_state: OBS media state (PLAYING, BUFFERING, etc.)
            media_time: Current media time in milliseconds
            obs_fps: OBS rendering FPS
            is_visible: Whether source is currently visible
            
        Returns:
            GStreamerHealthStatus with detailed health info
        """
        current_time = time.time()
        issues = []
        warnings = []
        
        # Initialize metrics
        media_time_progressing = True
        media_time_stall_duration = 0.0
        media_time_jitter = 0.0
        effective_framerate = None
        decode_lag_detected = False
        buffer_underrun_likely = False
        
        # 1. Check if media time is progressing
        if media_time is not None and self.last_media_time is not None:
            time_delta_ms = media_time - self.last_media_time
            real_time_delta_ms = (current_time - self.last_check_timestamp) * 1000
            
            # Track history
            self.media_time_history.append({
                'timestamp': current_time,
                'media_time': media_time,
                'time_delta_ms': time_delta_ms,
                'real_time_delta_ms': real_time_delta_ms
            })
            
            # Check for stall (media time not advancing)
            if media_state == "OBS_MEDIA_STATE_PLAYING":
                if time_delta_ms == 0:
                    media_time_progressing = False
                    
                    if self.stall_start_time is None:
                        self.stall_start_time = current_time
                        logger.warning(f"Media time stall detected at {media_time}ms")
                    
                    media_time_stall_duration = current_time - self.stall_start_time
                    
                    if media_time_stall_duration > 2.0:
                        issues.append(f"CRITICAL_MEDIA_STALL_{media_time_stall_duration:.1f}s")
                        buffer_underrun_likely = True
                    elif media_time_stall_duration > 0.5:
                        issues.append(f"MEDIA_STALL_{media_time_stall_duration:.1f}s")
                    else:
                        warnings.append(f"BRIEF_STALL_{int(media_time_stall_duration*1000)}ms")
                    
                    self.total_stalls += 1
                    self.stall_events.append(current_time)
                    
                else:
                    # Media time is progressing
                    if self.stall_start_time is not None:
                        stall_duration = current_time - self.stall_start_time
                        logger.info(f"Media time stall recovered after {stall_duration:.2f}s")
                        self.stall_start_time = None
                    
                    # Check for time jitter (irregular progression)
                    expected_delta_ms = real_time_delta_ms  # Should be ~1:1 for real-time
                    delta_error_ms = abs(time_delta_ms - expected_delta_ms)
                    
                    if delta_error_ms > self.jitter_threshold_ms:
                        media_time_jitter = delta_error_ms
                        
                        if time_delta_ms > expected_delta_ms * 1.5:
                            warnings.append(f"TIME_JUMP_FORWARD_{int(delta_error_ms)}ms")
                            decode_lag_detected = True
                        elif time_delta_ms < expected_delta_ms * 0.5:
                            warnings.append(f"TIME_JUMP_BACKWARD_{int(delta_error_ms)}ms")
                        
                        self.total_jitter_events += 1
                    
                    # Calculate effective framerate from media time progression
                    if len(self.media_time_history) >= 2:
                        recent_history = list(self.media_time_history)[-10:]  # Last 10 samples
                        time_span_real = recent_history[-1]['timestamp'] - recent_history[0]['timestamp']
                        time_span_media = recent_history[-1]['media_time'] - recent_history[0]['media_time']
                        
                        if time_span_real > 0 and time_span_media > 0:
                            # Effective framerate based on media time flow
                            effective_framerate = (time_span_media / time_span_real) * (obs_fps if obs_fps else 30) / 1000
        
        # 2. Interpret OBS media state with context
        if media_state and media_state != "OBS_MEDIA_STATE_PLAYING":
            if media_state == "OBS_MEDIA_STATE_BUFFERING":
                if media_time_progressing:
                    warnings.append("PIPELINE_BUFFERING_BUT_PROGRESSING")
                else:
                    issues.append("PIPELINE_BUFFERING")
                    buffer_underrun_likely = True
            elif media_state == "OBS_MEDIA_STATE_STOPPED":
                if media_time_progressing:
                    warnings.append("PIPELINE_STOPPED_BUT_PROGRESSING")
                else:
                    issues.append("PIPELINE_STOPPED")
                    buffer_underrun_likely = True
            elif media_state == "OBS_MEDIA_STATE_ERROR":
                if media_time_progressing:
                    warnings.append("MEDIA_STATE_ERROR_BUT_PROGRESSING")
                else:
                    issues.append("MEDIA_STATE_ERROR")
                    buffer_underrun_likely = True
            else:
                if not media_time_progressing:
                    issues.append(f"PIPELINE_STATE_{media_state}")
                else:
                    warnings.append(f"PIPELINE_STATE_{media_state}_BUT_PROGRESSING")
        
        # 3. Check for decode lag (FPS is good but media time jumpy)
        if obs_fps and obs_fps > 25 and media_time_jitter > 200:
            issues.append("DECODE_LAG_DETECTED")
            decode_lag_detected = True
        
        # 4. Check stall frequency
        stall_count_last_minute = sum(1 for t in self.stall_events if current_time - t < 60)
        if stall_count_last_minute > 5:
            issues.append(f"FREQUENT_STALLS_{stall_count_last_minute}/min")
            buffer_underrun_likely = True
        
        # 5. Check for "visible but not playing" (frozen frame)
        if is_visible and media_state != "OBS_MEDIA_STATE_PLAYING" and not media_time_progressing:
            issues.append(f"VISIBLE_NOT_PLAYING_{media_state}")
        
        # Calculate health score
        health_score = 100.0
        
        if not media_time_progressing:
            health_score -= 60  # Major issue
        
        if buffer_underrun_likely:
            health_score -= 30
        
        if decode_lag_detected:
            health_score -= 20
        
        if media_time_jitter > 200:
            health_score -= 15
        elif media_time_jitter > 100:
            health_score -= 5
        
        if stall_count_last_minute > 10:
            health_score -= 25
        elif stall_count_last_minute > 5:
            health_score -= 10
        
        health_score = max(0, health_score)
        
        # Determine health trend
        is_healthy = health_score > 70 and not issues
        
        if is_healthy:
            self.consecutive_healthy_checks += 1
            self.consecutive_unhealthy_checks = 0
        else:
            self.consecutive_unhealthy_checks += 1
            self.consecutive_healthy_checks = 0
        
        if self.consecutive_unhealthy_checks > 5:
            health_trend = "degrading"
        elif self.consecutive_healthy_checks > 10:
            health_trend = "improving"
        else:
            health_trend = "stable"
        
        # Update state for next check
        self.last_media_time = media_time
        self.last_check_timestamp = current_time
        
        return GStreamerHealthStatus(
            is_healthy=is_healthy,
            health_score=health_score,
            issues=issues,
            warnings=warnings,
            media_time_progressing=media_time_progressing,
            media_time_stall_duration=media_time_stall_duration,
            media_time_jitter=media_time_jitter,
            effective_framerate=effective_framerate,
            decode_lag_detected=decode_lag_detected,
            buffer_underrun_likely=buffer_underrun_likely,
            stall_count_last_minute=stall_count_last_minute,
            health_trend=health_trend
        )
    
    def get_diagnostics(self) -> Dict:
        """Get diagnostic information about GStreamer source health"""
        return {
            'total_stalls': self.total_stalls,
            'total_jitter_events': self.total_jitter_events,
            'stalls_last_minute': len(self.stall_events),
            'consecutive_healthy_checks': self.consecutive_healthy_checks,
            'consecutive_unhealthy_checks': self.consecutive_unhealthy_checks,
            'currently_stalled': self.stall_start_time is not None,
            'history_samples': len(self.media_time_history)
        }
    
    def reset(self):
        """Reset health checker state"""
        self.media_time_history.clear()
        self.stall_events.clear()
        self.last_media_time = None
        self.last_check_timestamp = None
        self.stall_start_time = None
        self.consecutive_healthy_checks = 0
        self.consecutive_unhealthy_checks = 0


def analyze_gstreamer_health_from_csv(csv_file: str) -> Dict:
    """
    Analyze GStreamer health from a stream-health CSV file.
    
    Useful for post-mortem analysis of choppy streams.
    
    Returns dict with:
        - stall_events: List of detected stalls
        - jitter_events: List of time jumps
        - health_timeline: Health score over time
        - recommendations: List of issues found
    """
    import pandas as pd
    
    df = pd.read_csv(csv_file)
    
    checker = GStreamerHealthChecker()
    stall_events = []
    jitter_events = []
    health_timeline = []
    
    for idx, row in df.iterrows():
        status = checker.check_health(
            media_state=row['media_state'],
            media_time=row['media_time'],
            obs_fps=row['obs_fps'],
            is_visible=row['is_visible']
        )
        
        health_timeline.append({
            'timestamp': row['timestamp'],
            'health_score': status.health_score,
            'is_healthy': status.is_healthy
        })
        
        if not status.media_time_progressing:
            stall_events.append({
                'timestamp': row['timestamp'],
                'timestamp_str': row['timestamp_str'],
                'media_time': row['media_time'],
                'duration': status.media_time_stall_duration
            })
        
        if status.media_time_jitter > 100:
            jitter_events.append({
                'timestamp': row['timestamp'],
                'timestamp_str': row['timestamp_str'],
                'jitter_ms': status.media_time_jitter
            })
    
    # Generate recommendations
    recommendations = []
    
    if len(stall_events) > 10:
        recommendations.append("CRITICAL: Frequent media time stalls detected - likely buffer underruns")
        recommendations.append("  → Increase GStreamer queue buffers (max-size-buffers)")
        recommendations.append("  → Check network stability to source")
        recommendations.append("  → Verify decode performance")
    
    if len(jitter_events) > 20:
        recommendations.append("WARNING: Frequent time jitter - irregular stream delivery")
        recommendations.append("  → Check source stream quality")
        recommendations.append("  → Consider enabling videorate/audiorate in pipeline")
        recommendations.append("  → Network jitter may be causing issues")
    
    avg_health = sum(h['health_score'] for h in health_timeline) / len(health_timeline) if health_timeline else 100
    if avg_health < 70:
        recommendations.append(f"Overall GStreamer health poor (avg: {avg_health:.1f}/100)")
        recommendations.append("  → Review pipeline configuration")
        recommendations.append("  → Check system resources during playback")
    
    return {
        'stall_events': stall_events,
        'jitter_events': jitter_events,
        'health_timeline': health_timeline,
        'recommendations': recommendations,
        'summary': {
            'total_stalls': len(stall_events),
            'total_jitter_events': len(jitter_events),
            'average_health_score': avg_health,
            'healthy_percentage': sum(1 for h in health_timeline if h['is_healthy']) / len(health_timeline) * 100 if health_timeline else 100
        }
    }

