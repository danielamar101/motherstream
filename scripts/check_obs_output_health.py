#!/usr/bin/env python3
"""
Quick OBS Output Health Checker

Connects to OBS and checks if the OUTPUT stream is healthy.
This catches high-load choppiness that input stream monitoring misses.

Run this DURING choppy playback to see if OBS is the bottleneck.
"""

import sys
import os
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from obswebsocket import obsws, requests
except ImportError:
    print("❌ Error: obswebsocket not installed")
    print("   Install with: pip install obs-websocket-py")
    sys.exit(1)


def check_obs_output(host='localhost', port=4455, password=None, duration=30, interval=2):
    """
    Check OBS output health for a duration
    
    Args:
        host: OBS websocket host
        port: OBS websocket port
        password: OBS websocket password
        duration: How long to monitor (seconds)
        interval: Seconds between checks
    """
    
    print("="*80)
    print("OBS OUTPUT HEALTH CHECKER")
    print("="*80)
    print(f"\n📡 Connecting to OBS at {host}:{port}...")
    
    try:
        ws = obsws(host, port, password)
        ws.connect()
        print("✅ Connected to OBS\n")
    except Exception as e:
        print(f"❌ Failed to connect to OBS: {e}")
        print("\nTroubleshooting:")
        print("  1. Is OBS running?")
        print("  2. Is OBS WebSocket plugin enabled?")
        print("  3. Check host/port/password in environment variables:")
        print(f"     OBS_HOST={host}")
        print(f"     OBS_PORT={port}")
        print(f"     OBS_PASSWORD={'*' * len(password) if password else 'None'}")
        sys.exit(1)
    
    print(f"⏱️  Monitoring for {duration} seconds (interval: {interval}s)")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    print("-"*80)
    
    # Baseline for rate calculations
    baseline_render_skipped = None
    baseline_output_skipped = None
    baseline_time = None
    
    # Track issues
    total_checks = 0
    degraded_checks = 0
    issues_seen = set()
    
    # Stats tracking
    fps_values = []
    frame_time_values = []
    render_skip_rates = []
    encoding_skip_rates = []
    
    start_time = time.time()
    
    try:
        while (time.time() - start_time) < duration:
            total_checks += 1
            
            try:
                # Get OBS stats
                response = ws.call(requests.GetStats())
                stats = response.datain
                
                current_time = time.time()
                
                # Extract metrics
                active_fps = stats.get('activeFps', 0)
                frame_time = stats.get('averageFrameRenderTime', 0)
                render_skipped = stats.get('renderSkippedFrames', 0)
                render_total = stats.get('renderTotalFrames', 0)
                output_skipped = stats.get('outputSkippedFrames', 0)
                output_total = stats.get('outputTotalFrames', 0)
                cpu_usage = stats.get('cpuUsage', 0)
                
                # Calculate skip rates
                render_skip_rate = 0
                encoding_skip_rate = 0
                
                if baseline_time is not None:
                    time_delta = current_time - baseline_time
                    
                    if time_delta > 0:
                        render_skip_delta = render_skipped - baseline_render_skipped
                        render_skip_rate = render_skip_delta / time_delta
                        
                        encoding_skip_delta = output_skipped - baseline_output_skipped
                        encoding_skip_rate = encoding_skip_delta / time_delta
                
                # Update baselines
                baseline_time = current_time
                baseline_render_skipped = render_skipped
                baseline_output_skipped = output_skipped
                
                # Track values
                if active_fps > 0:
                    fps_values.append(active_fps)
                if frame_time > 0:
                    frame_time_values.append(frame_time)
                if render_skip_rate > 0:
                    render_skip_rates.append(render_skip_rate)
                if encoding_skip_rate > 0:
                    encoding_skip_rates.append(encoding_skip_rate)
                
                # Analyze health
                issues = []
                is_degraded = False
                
                if active_fps < 25:
                    issues.append(f"CRITICAL_LOW_FPS_{active_fps:.1f}")
                    is_degraded = True
                elif active_fps < 28:
                    issues.append(f"LOW_FPS_{active_fps:.1f}")
                    is_degraded = True
                
                if frame_time > 50:
                    issues.append(f"CRITICAL_SLOW_RENDERING_{frame_time:.1f}ms")
                    is_degraded = True
                elif frame_time > 40:
                    issues.append(f"SLOW_RENDERING_{frame_time:.1f}ms")
                    is_degraded = True
                
                if render_skip_rate > 5:
                    issues.append(f"CRITICAL_RENDER_SKIPPING_{render_skip_rate:.1f}fps")
                    is_degraded = True
                elif render_skip_rate > 1:
                    issues.append(f"RENDER_SKIPPING_{render_skip_rate:.1f}fps")
                    is_degraded = True
                
                if encoding_skip_rate > 5:
                    issues.append(f"🚨 CRITICAL_ENCODING_SKIPPING_{encoding_skip_rate:.1f}fps")
                    is_degraded = True
                elif encoding_skip_rate > 1:
                    issues.append(f"⚠️  ENCODING_SKIPPING_{encoding_skip_rate:.1f}fps")
                    is_degraded = True
                
                # Display
                elapsed = time.time() - start_time
                status = "❌ DEGRADED" if is_degraded else "✅ HEALTHY"
                
                print(f"[{elapsed:5.1f}s] {status} | FPS: {active_fps:5.1f} | Frame: {frame_time:5.1f}ms | "
                      f"RenderSkip: {render_skip_rate:4.1f}/s | EncSkip: {encoding_skip_rate:4.1f}/s | CPU: {cpu_usage:5.1f}%")
                
                if issues:
                    print(f"         Issues: {', '.join(issues)}")
                    for issue in issues:
                        issues_seen.add(issue.replace('🚨 ', '').replace('⚠️  ', ''))
                    degraded_checks += 1
                
            except Exception as e:
                print(f"⚠️  Error getting stats: {e}")
            
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped by user")
    
    finally:
        ws.disconnect()
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total_time = time.time() - start_time
    degraded_percent = (degraded_checks / total_checks * 100) if total_checks > 0 else 0
    
    print(f"\nMonitoring Duration: {total_time:.1f} seconds")
    print(f"Total Checks: {total_checks}")
    print(f"Degraded Checks: {degraded_checks} ({degraded_percent:.1f}%)\n")
    
    if fps_values:
        print(f"FPS:")
        print(f"  Average: {sum(fps_values)/len(fps_values):.2f}")
        print(f"  Minimum: {min(fps_values):.2f}")
        print(f"  Maximum: {max(fps_values):.2f}\n")
    
    if frame_time_values:
        print(f"Frame Render Time:")
        print(f"  Average: {sum(frame_time_values)/len(frame_time_values):.2f}ms")
        print(f"  Maximum: {max(frame_time_values):.2f}ms\n")
    
    if render_skip_rates:
        print(f"Render Skip Rate:")
        print(f"  Average: {sum(render_skip_rates)/len(render_skip_rates):.2f} fps")
        print(f"  Peak: {max(render_skip_rates):.2f} fps\n")
    
    if encoding_skip_rates:
        print(f"Encoding Skip Rate:")
        print(f"  Average: {sum(encoding_skip_rates)/len(encoding_skip_rates):.2f} fps")
        print(f"  Peak: {max(encoding_skip_rates):.2f} fps\n")
    
    if issues_seen:
        print("Issues Detected:")
        for issue in sorted(issues_seen):
            print(f"  • {issue}")
        print()
    
    # Recommendations
    print("="*80)
    print("ANALYSIS & RECOMMENDATIONS")
    print("="*80 + "\n")
    
    if degraded_percent < 5:
        print("✅ OUTPUT QUALITY: EXCELLENT")
        print("   System is handling load well with minimal degradation.\n")
    elif degraded_percent < 20:
        print("⚠️  OUTPUT QUALITY: OCCASIONALLY DEGRADED")
        print("   System is near capacity. Consider:")
        print("   - Reducing concurrent stream count")
        print("   - Monitoring during peak load\n")
    else:
        print("❌ OUTPUT QUALITY: FREQUENTLY DEGRADED")
        print("   System is over capacity!\n")
    
    if encoding_skip_rates and max(encoding_skip_rates) > 5:
        print("🚨 CRITICAL: HIGH ENCODING SKIP RATE")
        print("   The encoder cannot keep up with the load (CPU bottleneck)")
        print("   This is causing the choppy video you're seeing!")
        print("\n   Immediate solutions:")
        print("   1. Reduce concurrent stream count")
        print("   2. Use faster encoder preset (veryfast, superfast, ultrafast)")
        print("   3. Enable hardware encoding (NVENC, QuickSync)")
        print("   4. Upgrade CPU\n")
    elif encoding_skip_rates and max(encoding_skip_rates) > 1:
        print("⚠️  WARNING: ENCODING SKIPPING DETECTED")
        print("   System is approaching encoding capacity")
        print("   Consider optimizing before adding more load\n")
    
    if render_skip_rates and max(render_skip_rates) > 5:
        print("⚠️  HIGH RENDER SKIP RATE")
        print("   Rendering cannot keep up")
        print("   Solutions:")
        print("   - Simplify scene complexity")
        print("   - Lower output resolution")
        print("   - Upgrade GPU\n")
    
    if fps_values and min(fps_values) < 25:
        print("⚠️  FPS DROPS DETECTED")
        print("   Output framerate dropped below acceptable threshold")
        print("   This causes visible stuttering to viewers\n")
    
    if frame_time_values and max(frame_time_values) > 50:
        print("⚠️  SLOW FRAME RENDERING")
        print("   Each frame is taking too long to render")
        print("   This indicates system overload\n")
    
    if not issues_seen:
        print("✅ NO ISSUES DETECTED")
        print("   If you're still seeing choppiness, the problem may be:")
        print("   - Network bandwidth saturation (check network_monitor.py)")
        print("   - Input stream quality issues (check stream health logs)")
        print("   - Viewer-side buffering\n")
    
    print("="*80)
    print("\n💡 For continuous monitoring, integrate obs_output_monitor.py into your app")
    print("📖 See docs/HIGH_LOAD_CHOPPINESS_GUIDE.md for detailed troubleshooting")
    print("="*80)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Check OBS output health to diagnose high-load choppiness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick 30-second check
  python check_obs_output_health.py
  
  # Extended 5-minute monitoring
  python check_obs_output_health.py --duration 300
  
  # Custom OBS connection
  python check_obs_output_health.py --host localhost --port 4455 --password mypass
  
  # Run during load test to see if OBS is bottleneck
  Terminal 1: python stream_load_tester.py --rtmp-url rtmp://localhost/live --max-streams 50
  Terminal 2: python check_obs_output_health.py --duration 120
        """
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default=os.environ.get('OBS_HOST', 'localhost'),
        help='OBS WebSocket host (default: localhost or $OBS_HOST)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.environ.get('OBS_PORT', 4455)),
        help='OBS WebSocket port (default: 4455 or $OBS_PORT)'
    )
    
    parser.add_argument(
        '--password',
        type=str,
        default=os.environ.get('OBS_PASSWORD'),
        help='OBS WebSocket password (default: $OBS_PASSWORD)'
    )
    
    parser.add_argument(
        '--duration',
        type=int,
        default=30,
        help='How long to monitor in seconds (default: 30)'
    )
    
    parser.add_argument(
        '--interval',
        type=float,
        default=2.0,
        help='Seconds between checks (default: 2.0)'
    )
    
    args = parser.parse_args()
    
    check_obs_output(
        host=args.host,
        port=args.port,
        password=args.password,
        duration=args.duration,
        interval=args.interval
    )


if __name__ == '__main__':
    main()

