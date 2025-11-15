#!/usr/bin/env python3
"""
Real-time Stream Monitoring Dashboard

Visualizes stream buffers, OBS performance, network stats, and system resources
in a beautiful terminal UI with live updates.
"""

import sys
import os
import time
import curses
from datetime import datetime
from collections import deque
from typing import Optional, Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from obswebsocket import obsws, requests as obs_requests
except ImportError:
    print("❌ Error: obswebsocket not installed")
    print("   Install with: pip install obs-websocket-py")
    sys.exit(1)

try:
    import psutil
except ImportError:
    print("❌ Error: psutil not installed")
    print("   Install with: pip install psutil")
    sys.exit(1)

# Import GStreamer health checker
try:
    from app.core.gstreamer_health_checker import GStreamerHealthChecker
    GSTREAMER_HEALTH_AVAILABLE = True
except ImportError:
    print("⚠️  Warning: GStreamer health checker not available")
    print("   GStreamer-specific checks will be disabled")
    GSTREAMER_HEALTH_AVAILABLE = False


class StreamDashboard:
    """Real-time monitoring dashboard for streams"""
    
    def __init__(self, obs_host='localhost', obs_port=4455, obs_password=None):
        self.obs_host = obs_host
        self.obs_port = obs_port
        self.obs_password = obs_password
        self.obs_ws = None
        
        # History for sparklines (last 60 data points)
        self.cpu_history = deque(maxlen=60)
        self.memory_history = deque(maxlen=60)
        self.fps_history = deque(maxlen=60)
        self.encoding_skip_history = deque(maxlen=60)
        self.bandwidth_history = deque(maxlen=60)
        self.gst_health_history = deque(maxlen=60)
        
        # Baselines for rate calculations
        self.last_net_io = None
        self.last_encoding_skipped = 0
        self.last_time = time.time()
        
        # GStreamer health checker
        self.gst_health_checker = GStreamerHealthChecker() if GSTREAMER_HEALTH_AVAILABLE else None
        self.current_source_name = None
        
        # Running status
        self.running = True
        self.error_message = None
        
    def connect_obs(self):
        """Connect to OBS WebSocket"""
        try:
            self.obs_ws = obsws(self.obs_host, self.obs_port, self.obs_password)
            self.obs_ws.connect()
            return True
        except Exception as e:
            self.error_message = f"OBS connection failed: {e}"
            return False
    
    def disconnect_obs(self):
        """Disconnect from OBS"""
        if self.obs_ws:
            try:
                self.obs_ws.disconnect()
            except:
                pass
    
    def get_obs_stats(self) -> Optional[Dict]:
        """Get OBS statistics"""
        if not self.obs_ws:
            return None
        
        try:
            response = self.obs_ws.call(obs_requests.GetStats())
            return response.datain
        except:
            return None
    
    def get_obs_streaming_status(self) -> Optional[Dict]:
        """Get OBS streaming status"""
        if not self.obs_ws:
            return None
        
        try:
            response = self.obs_ws.call(obs_requests.GetStreamStatus())
            return response.datain
        except:
            return None
    
    def get_current_source_status(self) -> Optional[Dict]:
        """Get current GStreamer source status"""
        if not self.obs_ws:
            return None
        
        try:
            # Get current scene
            scene_response = self.obs_ws.call(obs_requests.GetCurrentProgramScene())
            scene_name = scene_response.datain.get('currentProgramSceneName', 'MOTHERSTREAM')
            
            # Get scene items
            items_response = self.obs_ws.call(obs_requests.GetSceneItemList(sceneName=scene_name))
            scene_items = items_response.datain.get('sceneItems', [])
            
            # Find visible GStreamer source
            for item in scene_items:
                source_name = item.get('sourceName', '')
                if source_name.startswith('GMOTHERSTREAM_') and item.get('sceneItemEnabled', False):
                    # Found the active source
                    self.current_source_name = source_name
                    
                    # Get media status
                    try:
                        media_response = self.obs_ws.call(obs_requests.GetMediaInputStatus(inputName=source_name))
                        return media_response.datain
                    except:
                        return None
            
            return None
        except:
            return None
    
    def get_system_stats(self) -> Dict:
        """Get system resource statistics"""
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        
        # Network I/O
        net_io = psutil.net_io_counters()
        bandwidth_mbps = 0
        
        if self.last_net_io:
            time_delta = time.time() - self.last_time
            if time_delta > 0:
                bytes_sent = net_io.bytes_sent - self.last_net_io.bytes_sent
                bandwidth_mbps = (bytes_sent * 8) / (time_delta * 1_000_000)
        
        self.last_net_io = net_io
        self.last_time = time.time()
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used_gb': memory.used / (1024**3),
            'memory_total_gb': memory.total / (1024**3),
            'bandwidth_mbps': bandwidth_mbps,
            'network_errors': net_io.errin + net_io.errout,
            'network_drops': net_io.dropin + net_io.dropout
        }
    
    def draw_header(self, stdscr, y: int) -> int:
        """Draw header section"""
        height, width = stdscr.getmaxyx()
        
        # Title
        title = "🎥 MOTHERSTREAM - Real-Time Dashboard"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        stdscr.addstr(y, (width - len(title)) // 2, title, curses.A_BOLD)
        y += 1
        stdscr.addstr(y, width - len(timestamp) - 2, timestamp, curses.A_DIM)
        y += 1
        stdscr.addstr(y, 0, "═" * (width - 1))
        y += 2
        
        return y
    
    def draw_obs_section(self, stdscr, y: int, obs_stats: Optional[Dict], 
                         streaming_status: Optional[Dict]) -> int:
        """Draw OBS performance section"""
        height, width = stdscr.getmaxyx()
        
        stdscr.addstr(y, 0, "📊 OBS OUTPUT PERFORMANCE", curses.A_BOLD | curses.color_pair(3))
        y += 1
        stdscr.addstr(y, 0, "─" * (width - 1), curses.A_DIM)
        y += 1
        
        if not obs_stats:
            stdscr.addstr(y, 2, "❌ OBS not connected", curses.color_pair(1))
            if self.error_message:
                y += 1
                stdscr.addstr(y, 2, f"   {self.error_message}", curses.A_DIM)
            return y + 2
        
        # Extract metrics
        active_fps = obs_stats.get('activeFps', 0)
        frame_time = obs_stats.get('averageFrameRenderTime', 0)
        render_skipped = obs_stats.get('renderSkippedFrames', 0)
        render_total = obs_stats.get('renderTotalFrames', 0)
        output_skipped = obs_stats.get('outputSkippedFrames', 0)
        output_total = obs_stats.get('outputTotalFrames', 0)
        cpu_usage = obs_stats.get('cpuUsage', 0)
        memory_usage = obs_stats.get('memoryUsage', 0)
        
        # Calculate encoding skip rate
        encoding_skip_rate = 0
        if output_skipped > self.last_encoding_skipped:
            time_delta = time.time() - self.last_time
            if time_delta > 0:
                skip_delta = output_skipped - self.last_encoding_skipped
                encoding_skip_rate = skip_delta / time_delta
        self.last_encoding_skipped = output_skipped
        
        # Update histories
        self.fps_history.append(active_fps)
        self.encoding_skip_history.append(encoding_skip_rate)
        
        # Streaming status
        is_streaming = streaming_status.get('outputActive', False) if streaming_status else False
        stream_time = streaming_status.get('outputDuration', 0) if streaming_status else 0
        stream_time_str = f"{stream_time // 3600:02d}:{(stream_time % 3600) // 60:02d}:{stream_time % 60:02d}"
        
        # Status indicator
        if is_streaming:
            status_text = f"🔴 LIVE ({stream_time_str})"
            status_color = curses.color_pair(1)
        else:
            status_text = "⚪ OFFLINE"
            status_color = curses.A_DIM
        
        stdscr.addstr(y, 2, f"Status: {status_text}", status_color | curses.A_BOLD)
        y += 2
        
        # FPS
        fps_status = "✅" if active_fps >= 29 else "⚠️" if active_fps >= 25 else "❌"
        fps_color = curses.color_pair(2) if active_fps >= 29 else curses.color_pair(3) if active_fps >= 25 else curses.color_pair(1)
        stdscr.addstr(y, 2, f"{fps_status} FPS: ", fps_color)
        stdscr.addstr(f"{active_fps:5.1f}", fps_color | curses.A_BOLD)
        
        # FPS sparkline
        if len(self.fps_history) > 1:
            sparkline = self.create_sparkline(self.fps_history, width=30, max_val=31)
            stdscr.addstr(y, 30, sparkline, curses.A_DIM)
        y += 1
        
        # Frame time
        frame_status = "✅" if frame_time < 35 else "⚠️" if frame_time < 50 else "❌"
        frame_color = curses.color_pair(2) if frame_time < 35 else curses.color_pair(3) if frame_time < 50 else curses.color_pair(1)
        stdscr.addstr(y, 2, f"{frame_status} Frame Time: ", frame_color)
        stdscr.addstr(f"{frame_time:5.1f}ms", frame_color | curses.A_BOLD)
        stdscr.addstr(f"  (target: 33ms)", curses.A_DIM)
        y += 1
        
        # Encoding skip rate (CRITICAL METRIC)
        skip_status = "✅" if encoding_skip_rate < 0.5 else "⚠️" if encoding_skip_rate < 2 else "❌"
        skip_color = curses.color_pair(2) if encoding_skip_rate < 0.5 else curses.color_pair(3) if encoding_skip_rate < 2 else curses.color_pair(1)
        stdscr.addstr(y, 2, f"{skip_status} Encoding Skip: ", skip_color)
        stdscr.addstr(f"{encoding_skip_rate:4.1f} fps", skip_color | curses.A_BOLD)
        
        if encoding_skip_rate > 1.0:
            stdscr.addstr(f"  🚨 CHOPPY!", curses.color_pair(1) | curses.A_BOLD | curses.A_BLINK)
        
        # Sparkline
        if len(self.encoding_skip_history) > 1:
            sparkline = self.create_sparkline(self.encoding_skip_history, width=30, max_val=10)
            stdscr.addstr(y, 30, sparkline, curses.A_DIM)
        y += 1
        
        # Frame stats
        render_skip_percent = (render_skipped / render_total * 100) if render_total > 0 else 0
        output_skip_percent = (output_skipped / output_total * 100) if output_total > 0 else 0
        
        stdscr.addstr(y, 2, f"   Render Skipped: {render_skipped:,} ({render_skip_percent:.2f}%)", curses.A_DIM)
        y += 1
        stdscr.addstr(y, 2, f"   Output Skipped: {output_skipped:,} ({output_skip_percent:.2f}%)", curses.A_DIM)
        y += 2
        
        return y
    
    def draw_system_section(self, stdscr, y: int, system_stats: Dict) -> int:
        """Draw system resources section"""
        height, width = stdscr.getmaxyx()
        
        stdscr.addstr(y, 0, "💻 SYSTEM RESOURCES", curses.A_BOLD | curses.color_pair(3))
        y += 1
        stdscr.addstr(y, 0, "─" * (width - 1), curses.A_DIM)
        y += 1
        
        # Update histories
        self.cpu_history.append(system_stats['cpu_percent'])
        self.memory_history.append(system_stats['memory_percent'])
        self.bandwidth_history.append(system_stats['bandwidth_mbps'])
        
        # CPU
        cpu = system_stats['cpu_percent']
        cpu_status = "✅" if cpu < 70 else "⚠️" if cpu < 85 else "❌"
        cpu_color = curses.color_pair(2) if cpu < 70 else curses.color_pair(3) if cpu < 85 else curses.color_pair(1)
        stdscr.addstr(y, 2, f"{cpu_status} CPU: ", cpu_color)
        stdscr.addstr(f"{cpu:5.1f}%", cpu_color | curses.A_BOLD)
        
        # CPU bar
        bar = self.create_bar(cpu, 100, width=30)
        stdscr.addstr(y, 20, bar, cpu_color)
        
        # Sparkline
        if len(self.cpu_history) > 1:
            sparkline = self.create_sparkline(self.cpu_history, width=20, max_val=100)
            stdscr.addstr(y, 52, sparkline, curses.A_DIM)
        y += 1
        
        # Memory
        mem = system_stats['memory_percent']
        mem_status = "✅" if mem < 75 else "⚠️" if mem < 90 else "❌"
        mem_color = curses.color_pair(2) if mem < 75 else curses.color_pair(3) if mem < 90 else curses.color_pair(1)
        stdscr.addstr(y, 2, f"{mem_status} Memory: ", mem_color)
        stdscr.addstr(f"{mem:5.1f}%", mem_color | curses.A_BOLD)
        stdscr.addstr(f" ({system_stats['memory_used_gb']:.1f}/{system_stats['memory_total_gb']:.1f} GB)", curses.A_DIM)
        
        # Memory bar
        bar = self.create_bar(mem, 100, width=30)
        stdscr.addstr(y, 20, bar, mem_color)
        y += 1
        
        # Network
        bw = system_stats['bandwidth_mbps']
        bw_status = "✅" if bw < 800 else "⚠️" if bw < 900 else "❌"
        bw_color = curses.color_pair(2) if bw < 800 else curses.color_pair(3) if bw < 900 else curses.color_pair(1)
        stdscr.addstr(y, 2, f"📡 Upload: ", bw_color)
        stdscr.addstr(f"{bw:7.2f} Mbps", bw_color | curses.A_BOLD)
        
        # Bandwidth sparkline
        if len(self.bandwidth_history) > 1:
            sparkline = self.create_sparkline(self.bandwidth_history, width=30, max_val=1000)
            stdscr.addstr(y, 30, sparkline, curses.A_DIM)
        y += 1
        
        # Network errors
        if system_stats['network_errors'] > 0 or system_stats['network_drops'] > 0:
            stdscr.addstr(y, 2, f"   ⚠️  Errors: {system_stats['network_errors']} | Drops: {system_stats['network_drops']}", 
                         curses.color_pair(3))
            y += 1
        
        y += 1
        return y
    
    def draw_gstreamer_section(self, stdscr, y: int, source_status: Optional[Dict], obs_stats: Optional[Dict]) -> int:
        """Draw GStreamer source health section"""
        height, width = stdscr.getmaxyx()
        
        stdscr.addstr(y, 0, "🎬 GSTREAMER SOURCE HEALTH", curses.A_BOLD | curses.color_pair(3))
        y += 1
        stdscr.addstr(y, 0, "─" * (width - 1), curses.A_DIM)
        y += 1
        
        if not self.gst_health_checker:
            stdscr.addstr(y, 2, "⚠️  GStreamer health checker not available", curses.A_DIM)
            return y + 2
        
        if not source_status:
            stdscr.addstr(y, 2, "⚪ No active GStreamer source", curses.A_DIM)
            return y + 2
        
        # Extract source info
        media_state = source_status.get('mediaState')
        media_time = source_status.get('mediaTime') or source_status.get('mediaCursor')
        obs_fps = obs_stats.get('activeFps') if obs_stats else None
        
        # Check GStreamer health
        gst_health = self.gst_health_checker.check_health(
            media_state=media_state,
            media_time=media_time,
            obs_fps=obs_fps,
            is_visible=True  # Assume visible if we got status
        )
        
        # Update history
        self.gst_health_history.append(gst_health.health_score)
        
        # Show source name
        if self.current_source_name:
            stdscr.addstr(y, 2, f"Source: {self.current_source_name}", curses.A_DIM)
            y += 1
        
        # Overall health status
        if gst_health.is_healthy:
            status_text = "✅ HEALTHY"
            status_color = curses.color_pair(2)
        else:
            status_text = "❌ UNHEALTHY"
            status_color = curses.color_pair(1) | curses.A_BOLD
        
        stdscr.addstr(y, 2, f"Status: {status_text}", status_color)
        stdscr.addstr(f"  (Score: {gst_health.health_score:.0f}/100)", status_color)
        y += 1
        
        # Health score sparkline
        if len(self.gst_health_history) > 1:
            sparkline = self.create_sparkline(self.gst_health_history, width=50, max_val=100)
            stdscr.addstr(y, 2, "Health: " + sparkline, curses.A_DIM)
            y += 1
        
        y += 1
        
        # Media time progression
        prog_status = "✅" if gst_health.media_time_progressing else "❌"
        prog_color = curses.color_pair(2) if gst_health.media_time_progressing else curses.color_pair(1)
        stdscr.addstr(y, 2, f"{prog_status} Media Time: ", prog_color)
        
        if gst_health.media_time_progressing:
            stdscr.addstr("Progressing", prog_color)
        else:
            stdscr.addstr(f"STALLED {gst_health.media_time_stall_duration:.1f}s", prog_color | curses.A_BOLD)
        
        if media_time is not None:
            stdscr.addstr(f"  ({media_time}ms)", curses.A_DIM)
        y += 1
        
        # Effective framerate
        if gst_health.effective_framerate:
            stdscr.addstr(y, 2, f"   Effective FPS: {gst_health.effective_framerate:.1f}", curses.A_DIM)
            y += 1
        
        # Time jitter
        if gst_health.media_time_jitter > 0:
            jitter_color = curses.color_pair(3) if gst_health.media_time_jitter < 200 else curses.color_pair(1)
            stdscr.addstr(y, 2, f"⚠️  Time Jitter: {gst_health.media_time_jitter:.0f}ms", jitter_color)
            y += 1
        
        # Buffer underrun
        if gst_health.buffer_underrun_likely:
            stdscr.addstr(y, 2, "🚨 Buffer Underrun Detected", curses.color_pair(1) | curses.A_BOLD)
            y += 1
        
        # Decode lag
        if gst_health.decode_lag_detected:
            stdscr.addstr(y, 2, "⚠️  Decode Lag Detected", curses.color_pair(3))
            y += 1
        
        # Stall frequency
        if gst_health.stall_count_last_minute > 0:
            stall_color = curses.color_pair(3) if gst_health.stall_count_last_minute < 5 else curses.color_pair(1)
            stdscr.addstr(y, 2, f"   Stalls (1min): {gst_health.stall_count_last_minute}", stall_color)
            y += 1
        
        # Issues
        if gst_health.issues:
            y += 1
            stdscr.addstr(y, 2, "🚨 Issues:", curses.color_pair(1) | curses.A_BOLD)
            y += 1
            for issue in gst_health.issues[:3]:  # Show top 3
                stdscr.addstr(y, 4, f"• {issue}", curses.color_pair(1))
                y += 1
        
        # Warnings
        if gst_health.warnings and not gst_health.issues:
            y += 1
            stdscr.addstr(y, 2, "⚠️  Warnings:", curses.color_pair(3))
            y += 1
            for warning in gst_health.warnings[:2]:  # Show top 2
                stdscr.addstr(y, 4, f"• {warning}", curses.color_pair(3))
                y += 1
        
        y += 1
        return y
    
    def draw_buffer_section(self, stdscr, y: int, obs_stats: Optional[Dict]) -> int:
        """Draw stream buffer visualization"""
        height, width = stdscr.getmaxyx()
        
        stdscr.addstr(y, 0, "📦 PIPELINE BUFFERS", curses.A_BOLD | curses.color_pair(3))
        y += 1
        stdscr.addstr(y, 0, "─" * (width - 1), curses.A_DIM)
        y += 1
        
        if not obs_stats:
            stdscr.addstr(y, 2, "❌ Buffer info unavailable (OBS not connected)", curses.A_DIM)
            return y + 2
        
        # Render queue (inferred from frame time)
        frame_time = obs_stats.get('averageFrameRenderTime', 0)
        render_pressure = min(frame_time / 50.0, 1.0)  # 50ms = 100% pressure
        
        stdscr.addstr(y, 2, "Render Pipeline: ")
        bar = self.create_bar(render_pressure * 100, 100, width=40, filled_char='█', empty_char='░')
        if render_pressure < 0.7:
            color = curses.color_pair(2)
        elif render_pressure < 0.9:
            color = curses.color_pair(3)
        else:
            color = curses.color_pair(1)
        stdscr.addstr(bar, color)
        stdscr.addstr(f" {render_pressure*100:.0f}%", color)
        y += 1
        
        # Encoding queue (inferred from skip rate)
        encoding_skip_rate = self.encoding_skip_history[-1] if self.encoding_skip_history else 0
        encoding_pressure = min(encoding_skip_rate / 10.0, 1.0)  # 10fps skip = 100% pressure
        
        stdscr.addstr(y, 2, "Encoding Queue:  ")
        bar = self.create_bar(encoding_pressure * 100, 100, width=40, filled_char='█', empty_char='░')
        if encoding_pressure < 0.1:
            color = curses.color_pair(2)
        elif encoding_pressure < 0.5:
            color = curses.color_pair(3)
        else:
            color = curses.color_pair(1)
        stdscr.addstr(bar, color)
        stdscr.addstr(f" {encoding_pressure*100:.0f}%", color)
        y += 1
        
        y += 1
        return y
    
    def draw_footer(self, stdscr, y: int) -> int:
        """Draw footer with controls"""
        height, width = stdscr.getmaxyx()
        
        footer_y = height - 2
        stdscr.addstr(footer_y, 0, "─" * (width - 1), curses.A_DIM)
        footer_y += 1
        
        controls = "Press 'q' to quit | Refreshes every 1 second"
        stdscr.addstr(footer_y, (width - len(controls)) // 2, controls, curses.A_DIM)
        
        return footer_y
    
    def create_bar(self, value: float, max_val: float, width: int = 20, 
                   filled_char: str = '█', empty_char: str = '░') -> str:
        """Create a progress bar"""
        filled = int((value / max_val) * width)
        empty = width - filled
        return filled_char * filled + empty_char * empty
    
    def create_sparkline(self, values: deque, width: int = 20, max_val: float = 100) -> str:
        """Create a sparkline chart"""
        if not values or len(values) < 2:
            return ""
        
        # Sparkline characters (from low to high)
        chars = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
        
        # Sample values to fit width
        step = max(1, len(values) // width)
        sampled = [values[i] for i in range(0, len(values), step)][-width:]
        
        # Create sparkline
        result = []
        for val in sampled:
            normalized = min(val / max_val, 1.0)
            char_idx = int(normalized * (len(chars) - 1))
            result.append(chars[char_idx])
        
        return ''.join(result)
    
    def run(self, stdscr):
        """Main dashboard loop"""
        # Setup curses
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(1)   # Non-blocking input
        stdscr.timeout(100) # 100ms timeout
        
        # Setup colors
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        
        # Connect to OBS
        self.connect_obs()
        
        last_update = 0
        update_interval = 1.0  # Update every second
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check for quit
                try:
                    key = stdscr.getch()
                    if key == ord('q') or key == ord('Q'):
                        self.running = False
                        break
                except:
                    pass
                
                # Update data
                if current_time - last_update >= update_interval:
                    stdscr.clear()
                    
                    # Get data
                    obs_stats = self.get_obs_stats()
                    streaming_status = self.get_obs_streaming_status()
                    source_status = self.get_current_source_status()
                    system_stats = self.get_system_stats()
                    
                    # Draw sections
                    y = 0
                    y = self.draw_header(stdscr, y)
                    y = self.draw_obs_section(stdscr, y, obs_stats, streaming_status)
                    y = self.draw_gstreamer_section(stdscr, y, source_status, obs_stats)
                    y = self.draw_system_section(stdscr, y, system_stats)
                    y = self.draw_buffer_section(stdscr, y, obs_stats)
                    self.draw_footer(stdscr, y)
                    
                    stdscr.refresh()
                    last_update = current_time
                
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                # Show error but keep running
                self.error_message = str(e)
        
        # Cleanup
        self.disconnect_obs()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Real-time stream monitoring dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start dashboard
  python stream_dashboard.py
  
  # With custom OBS connection
  python stream_dashboard.py --host localhost --port 4455 --password mypass

Controls:
  q - Quit dashboard
        """
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default=os.environ.get('OBS_HOST', 'localhost'),
        help='OBS WebSocket host'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.environ.get('OBS_PORT', 4455)),
        help='OBS WebSocket port'
    )
    
    parser.add_argument(
        '--password',
        type=str,
        default=os.environ.get('OBS_PASSWORD'),
        help='OBS WebSocket password'
    )
    
    args = parser.parse_args()
    
    dashboard = StreamDashboard(
        obs_host=args.host,
        obs_port=args.port,
        obs_password=args.password
    )
    
    try:
        curses.wrapper(dashboard.run)
    except KeyboardInterrupt:
        pass
    
    print("\n✅ Dashboard closed")


if __name__ == '__main__':
    main()

