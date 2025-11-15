#!/usr/bin/env python3
"""
Stream Load Tester - Simulate multiple concurrent streamers
Helps determine the maximum capacity of your streaming infrastructure.
"""

import subprocess
import time
import threading
import argparse
import sys
import os
import signal
from datetime import datetime
from typing import List, Dict
import json

class StreamSimulator:
    """Simulates a single stream using ffmpeg"""
    
    def __init__(self, stream_id: int, rtmp_url: str, stream_key: str, 
                 resolution: str = "1280x720", fps: int = 30, bitrate: str = "2500k"):
        self.stream_id = stream_id
        self.rtmp_url = rtmp_url
        self.stream_key = f"{stream_key}_{stream_id}"
        self.resolution = resolution
        self.fps = fps
        self.bitrate = bitrate
        self.process = None
        self.start_time = None
        self.is_running = False
        self.error = None
        
    def start(self):
        """Start the simulated stream"""
        # Generate test pattern with ffmpeg
        # Using lavfi testsrc2 for realistic video load
        cmd = [
            'ffmpeg',
            '-re',  # Real-time
            '-f', 'lavfi',
            '-i', f'testsrc2=size={self.resolution}:rate={self.fps}',
            '-f', 'lavfi',
            '-i', 'sine=frequency=1000:sample_rate=44100',  # Audio tone
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-b:v', self.bitrate,
            '-maxrate', self.bitrate,
            '-bufsize', f'{int(self.bitrate[:-1]) * 2}k',
            '-pix_fmt', 'yuv420p',
            '-g', str(self.fps * 2),  # Keyframe interval
            '-c:a', 'aac',
            '-b:a', '128k',
            '-f', 'flv',
            f'{self.rtmp_url}/{self.stream_key}'
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE
            )
            self.start_time = time.time()
            self.is_running = True
            print(f"✅ Stream {self.stream_id} started: {self.stream_key}")
        except Exception as e:
            self.error = str(e)
            self.is_running = False
            print(f"❌ Stream {self.stream_id} failed to start: {e}")
    
    def stop(self):
        """Stop the simulated stream"""
        if self.process:
            try:
                # Send 'q' to ffmpeg for graceful shutdown
                self.process.stdin.write(b'q')
                self.process.stdin.flush()
                self.process.wait(timeout=5)
            except:
                # Force kill if graceful shutdown fails
                self.process.kill()
                self.process.wait()
            
            self.is_running = False
            duration = time.time() - self.start_time if self.start_time else 0
            print(f"⏹️  Stream {self.stream_id} stopped (ran for {duration:.1f}s)")
    
    def check_status(self) -> bool:
        """Check if stream is still running"""
        if not self.process:
            return False
        
        poll = self.process.poll()
        if poll is not None:
            # Process has terminated
            self.is_running = False
            if poll != 0:
                stderr = self.process.stderr.read().decode('utf-8', errors='ignore')
                self.error = f"Exit code {poll}: {stderr[-500:]}"  # Last 500 chars
                print(f"⚠️  Stream {self.stream_id} terminated unexpectedly: {self.error[:100]}")
        
        return self.is_running


class LoadTester:
    """Manages multiple simulated streams for load testing"""
    
    def __init__(self, rtmp_url: str, stream_key_prefix: str = "test_stream",
                 max_streams: int = 10, ramp_up_interval: int = 5,
                 resolution: str = "1280x720", fps: int = 30, bitrate: str = "2500k"):
        self.rtmp_url = rtmp_url
        self.stream_key_prefix = stream_key_prefix
        self.max_streams = max_streams
        self.ramp_up_interval = ramp_up_interval
        self.resolution = resolution
        self.fps = fps
        self.bitrate = bitrate
        
        self.simulators: List[StreamSimulator] = []
        self.running = False
        self.start_time = None
        
        # Statistics
        self.stats = {
            'streams_started': 0,
            'streams_failed': 0,
            'streams_crashed': 0,
            'max_concurrent': 0
        }
    
    def create_stream(self, stream_id: int) -> StreamSimulator:
        """Create a new stream simulator"""
        return StreamSimulator(
            stream_id=stream_id,
            rtmp_url=self.rtmp_url,
            stream_key=self.stream_key_prefix,
            resolution=self.resolution,
            fps=self.fps,
            bitrate=self.bitrate
        )
    
    def ramp_up(self):
        """Gradually increase the number of concurrent streams"""
        print(f"\n🚀 Starting load test: ramping up to {self.max_streams} concurrent streams")
        print(f"📊 Stream settings: {self.resolution} @ {self.fps}fps, {self.bitrate} bitrate")
        print(f"⏱️  Ramp-up interval: {self.ramp_up_interval} seconds between streams")
        print(f"🎯 Target: {self.rtmp_url}\n")
        
        self.start_time = time.time()
        self.running = True
        
        for i in range(self.max_streams):
            if not self.running:
                break
            
            # Create and start stream
            simulator = self.create_stream(i + 1)
            simulator.start()
            
            if simulator.is_running:
                self.simulators.append(simulator)
                self.stats['streams_started'] += 1
            else:
                self.stats['streams_failed'] += 1
            
            # Update max concurrent
            active_count = self.get_active_count()
            self.stats['max_concurrent'] = max(self.stats['max_concurrent'], active_count)
            
            print(f"📈 Active streams: {active_count}/{self.max_streams}")
            
            # Wait before starting next stream
            if i < self.max_streams - 1:
                time.sleep(self.ramp_up_interval)
    
    def monitor(self, duration: int = None):
        """Monitor active streams"""
        print(f"\n👁️  Monitoring streams...")
        if duration:
            print(f"⏰ Will monitor for {duration} seconds")
        else:
            print("⏰ Press Ctrl+C to stop")
        
        start_monitor = time.time()
        
        try:
            while self.running:
                # Check duration
                if duration and (time.time() - start_monitor) >= duration:
                    print("\n⏰ Monitoring duration reached")
                    break
                
                # Check stream status
                active_count = 0
                for simulator in self.simulators:
                    if simulator.check_status():
                        active_count += 1
                    elif simulator.is_running == False and simulator not in self.get_crashed_streams():
                        self.stats['streams_crashed'] += 1
                
                self.stats['max_concurrent'] = max(self.stats['max_concurrent'], active_count)
                
                # Print status every 10 seconds
                elapsed = time.time() - self.start_time
                print(f"⏱️  [{elapsed:.0f}s] Active: {active_count}/{len(self.simulators)}, "
                      f"Crashed: {self.stats['streams_crashed']}")
                
                time.sleep(10)
                
        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")
    
    def get_active_count(self) -> int:
        """Get number of currently active streams"""
        return sum(1 for s in self.simulators if s.is_running)
    
    def get_crashed_streams(self) -> List[StreamSimulator]:
        """Get list of crashed streams"""
        return [s for s in self.simulators if not s.is_running and s.start_time]
    
    def shutdown(self):
        """Shutdown all streams"""
        print("\n🛑 Shutting down all streams...")
        self.running = False
        
        for simulator in self.simulators:
            simulator.stop()
        
        print("✅ All streams stopped")
    
    def print_report(self):
        """Print final test report"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        print("\n" + "="*80)
        print("LOAD TEST REPORT")
        print("="*80)
        print(f"\nTest Duration: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print(f"\nStream Configuration:")
        print(f"  Resolution: {self.resolution}")
        print(f"  FPS:        {self.fps}")
        print(f"  Bitrate:    {self.bitrate}")
        print(f"\nResults:")
        print(f"  Total Streams Attempted: {self.stats['streams_started']}")
        print(f"  Failed to Start:         {self.stats['streams_failed']}")
        print(f"  Crashed During Test:     {self.stats['streams_crashed']}")
        print(f"  Max Concurrent:          {self.stats['max_concurrent']}")
        print(f"  Final Active:            {self.get_active_count()}")
        
        success_rate = ((self.stats['streams_started'] - self.stats['streams_failed'] - self.stats['streams_crashed']) 
                       / self.stats['streams_started'] * 100) if self.stats['streams_started'] > 0 else 0
        print(f"  Success Rate:            {success_rate:.1f}%")
        
        # Bandwidth estimate
        try:
            bitrate_mbps = float(self.bitrate.rstrip('kK')) / 1000
            total_bandwidth = bitrate_mbps * self.stats['max_concurrent']
            print(f"\nEstimated Peak Bandwidth: {total_bandwidth:.2f} Mbps (upload)")
        except:
            pass
        
        if self.get_crashed_streams():
            print(f"\n⚠️  Crashes detected! Check system logs and network monitor output.")
            print(f"   Last successful count: {self.stats['max_concurrent']}")
        
        print("\n💡 RECOMMENDATIONS:")
        if self.stats['max_concurrent'] < self.max_streams:
            print(f"   • System reached capacity at ~{self.stats['max_concurrent']} concurrent streams")
            print(f"   • Consider running network_monitor.py to identify bottlenecks")
        else:
            print(f"   • System handled all {self.max_streams} streams successfully")
            print(f"   • You may be able to handle more - try increasing --max-streams")
        
        print("="*80 + "\n")


def check_ffmpeg():
    """Check if ffmpeg is available"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              timeout=5)
        return result.returncode == 0
    except:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Stream Load Tester - Simulate multiple concurrent streamers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with 10 streams on local SRS server
  python stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 10
  
  # Aggressive test: 50 streams with fast ramp-up
  python stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 50 --ramp-up 2
  
  # Lower quality streams for testing connection capacity
  python stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 100 \\
    --resolution 640x360 --fps 24 --bitrate 1000k
  
  # Monitor for specific duration after ramp-up
  python stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 20 \\
    --monitor-duration 300
  
  # Run alongside network_monitor.py:
  Terminal 1: python network_monitor.py --interval 5
  Terminal 2: python stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 50
        """
    )
    
    parser.add_argument(
        '--rtmp-url',
        type=str,
        required=True,
        help='RTMP server URL (e.g., rtmp://localhost/live)'
    )
    
    parser.add_argument(
        '--stream-key-prefix',
        type=str,
        default='test_stream',
        help='Prefix for stream keys (default: test_stream)'
    )
    
    parser.add_argument(
        '--max-streams',
        type=int,
        default=10,
        help='Maximum number of concurrent streams (default: 10)'
    )
    
    parser.add_argument(
        '--ramp-up',
        type=int,
        default=5,
        help='Seconds between starting each stream (default: 5)'
    )
    
    parser.add_argument(
        '--monitor-duration',
        type=int,
        help='How long to monitor after ramp-up in seconds (default: indefinite)'
    )
    
    parser.add_argument(
        '--resolution',
        type=str,
        default='1280x720',
        help='Stream resolution (default: 1280x720)'
    )
    
    parser.add_argument(
        '--fps',
        type=int,
        default=30,
        help='Frames per second (default: 30)'
    )
    
    parser.add_argument(
        '--bitrate',
        type=str,
        default='2500k',
        help='Video bitrate (default: 2500k)'
    )
    
    args = parser.parse_args()
    
    # Check for ffmpeg
    if not check_ffmpeg():
        print("❌ Error: ffmpeg not found. Please install ffmpeg first.")
        print("   Ubuntu/Debian: sudo apt install ffmpeg")
        print("   Fedora: sudo dnf install ffmpeg")
        print("   macOS: brew install ffmpeg")
        sys.exit(1)
    
    # Create load tester
    tester = LoadTester(
        rtmp_url=args.rtmp_url,
        stream_key_prefix=args.stream_key_prefix,
        max_streams=args.max_streams,
        ramp_up_interval=args.ramp_up,
        resolution=args.resolution,
        fps=args.fps,
        bitrate=args.bitrate
    )
    
    # Setup signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\n\n⏸️  Received interrupt signal")
        tester.shutdown()
        tester.print_report()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Ramp up streams
        tester.ramp_up()
        
        # Monitor
        tester.monitor(duration=args.monitor_duration)
        
        # Shutdown
        tester.shutdown()
        
    except Exception as e:
        print(f"\n❌ Error during load test: {e}")
        tester.shutdown()
    
    finally:
        # Print final report
        tester.print_report()


if __name__ == '__main__':
    main()

