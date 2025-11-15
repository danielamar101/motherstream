#!/usr/bin/env python3
"""
Analyze GStreamer Source Health from CSV Logs

Detects "invisible" issues that cause choppy playback:
- Media time stalls (frozen frames)
- Time jitter (irregular progression)
- Buffer underruns
- Decode lag

Run this on your stream-health CSV files to see why streams were choppy
even though health checks said everything was fine!
"""

import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from app.core.gstreamer_health_checker import analyze_gstreamer_health_from_csv
except ImportError:
    print("❌ Error: Could not import gstreamer_health_checker")
    print("   Make sure you're running from the motherstream directory")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("❌ Error: pandas not installed")
    print("   Install with: pip install pandas")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze GStreamer source health from stream-health CSV logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze today's stream
  python analyze_gstreamer_health.py ../docker-volume-mounts/logs/stream-metrics/stream-health-20251114-190000.csv
  
  # Analyze with detailed output
  python analyze_gstreamer_health.py --verbose stream-health.csv
  
  # Find the worst issues
  python analyze_gstreamer_health.py --show-worst 10 stream-health.csv
        """
    )
    
    parser.add_argument(
        'csv_file',
        type=str,
        help='Path to stream-health CSV file'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed events'
    )
    
    parser.add_argument(
        '--show-worst',
        type=int,
        metavar='N',
        help='Show N worst stall/jitter events'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        print(f"❌ File not found: {args.csv_file}")
        sys.exit(1)
    
    print("="*80)
    print("GSTREAMER SOURCE HEALTH ANALYSIS")
    print("="*80)
    print(f"\n📁 File: {args.csv_file}\n")
    
    # Analyze
    print("🔍 Analyzing GStreamer health...")
    result = analyze_gstreamer_health_from_csv(args.csv_file)
    
    # Summary
    summary = result['summary']
    print("\n📊 SUMMARY:")
    print("-"*80)
    print(f"Total Stall Events: {summary['total_stalls']}")
    print(f"Total Jitter Events: {summary['total_jitter_events']}")
    print(f"Average Health Score: {summary['average_health_score']:.1f}/100")
    print(f"Healthy Percentage: {summary['healthy_percentage']:.1f}%")
    
    # Show worst stalls
    if args.show_worst and result['stall_events']:
        print(f"\n🚨 WORST {args.show_worst} STALL EVENTS:")
        print("-"*80)
        sorted_stalls = sorted(result['stall_events'], 
                              key=lambda x: x['duration'], 
                              reverse=True)[:args.show_worst]
        
        for event in sorted_stalls:
            print(f"  {event['timestamp_str']}: Media time stuck at {event['media_time']}ms "
                  f"for {event['duration']:.2f}s")
    
    # Show worst jitter
    if args.show_worst and result['jitter_events']:
        print(f"\n⚠️  WORST {args.show_worst} JITTER EVENTS:")
        print("-"*80)
        sorted_jitter = sorted(result['jitter_events'],
                              key=lambda x: x['jitter_ms'],
                              reverse=True)[:args.show_worst]
        
        for event in sorted_jitter:
            print(f"  {event['timestamp_str']}: Time jump of {event['jitter_ms']:.0f}ms")
    
    # Verbose mode
    if args.verbose:
        print("\n📈 HEALTH TIMELINE:")
        print("-"*80)
        for i, point in enumerate(result['health_timeline']):
            if i % 10 == 0:  # Show every 10th sample
                status = "✅" if point['is_healthy'] else "❌"
                print(f"  Sample {i}: {status} Score: {point['health_score']:.0f}/100")
    
    # Recommendations
    if result['recommendations']:
        print("\n💡 RECOMMENDATIONS:")
        print("-"*80)
        for rec in result['recommendations']:
            print(f"  {rec}")
    else:
        print("\n✅ NO MAJOR ISSUES DETECTED")
        print("   GStreamer source appears healthy")
    
    # Visual summary
    print("\n" + "="*80)
    if summary['healthy_percentage'] < 50:
        print("🚨 CRITICAL: GStreamer source was unhealthy most of the time!")
        print("   This explains the choppy playback you experienced.")
    elif summary['healthy_percentage'] < 80:
        print("⚠️  WARNING: GStreamer source had frequent health issues")
        print("   This likely caused noticeable choppiness")
    else:
        print("✅ GOOD: GStreamer source was mostly healthy")
        print("   If you experienced choppiness, check OBS output performance")
    
    print("="*80)
    
    # Exit code based on health
    if summary['healthy_percentage'] < 50:
        sys.exit(2)  # Critical
    elif summary['healthy_percentage'] < 80:
        sys.exit(1)  # Warning
    else:
        sys.exit(0)  # OK


if __name__ == '__main__':
    main()

