#!/usr/bin/env python3
"""
Analyze and visualize network monitoring data
Generates reports and plots from CSV logs
"""

import pandas as pd
import argparse
import sys
import os
from datetime import datetime
import glob

def analyze_csv(csv_file: str):
    """Analyze a monitoring CSV file"""
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        return
    
    # Load data
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return
    
    if len(df) == 0:
        print("❌ CSV file is empty")
        return
    
    print("="*80)
    print(f"ANALYSIS: {os.path.basename(csv_file)}")
    print("="*80)
    
    # Basic info
    duration = df['elapsed_seconds'].max()
    samples = len(df)
    
    print(f"\n📊 Dataset Info:")
    print(f"  Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"  Samples:  {samples}")
    print(f"  Interval: ~{duration/samples:.1f} seconds")
    
    # Bandwidth statistics
    print(f"\n📡 Bandwidth (Mbps):")
    print(f"  Upload:")
    print(f"    Average: {df['upload_mbps'].mean():8.2f}")
    print(f"    Peak:    {df['upload_mbps'].max():8.2f}")
    print(f"    Min:     {df['upload_mbps'].min():8.2f}")
    print(f"  Download:")
    print(f"    Average: {df['download_mbps'].mean():8.2f}")
    print(f"    Peak:    {df['download_mbps'].max():8.2f}")
    print(f"    Min:     {df['download_mbps'].min():8.2f}")
    
    # Connection statistics
    print(f"\n🔌 Connections:")
    print(f"  Established:")
    print(f"    Average: {df['established_connections'].mean():8.1f}")
    print(f"    Peak:    {df['established_connections'].max():8.0f}")
    print(f"    Min:     {df['established_connections'].min():8.0f}")
    print(f"  RTMP:")
    print(f"    Average: {df['rtmp_connections'].mean():8.1f}")
    print(f"    Peak:    {df['rtmp_connections'].max():8.0f}")
    
    # System resources
    print(f"\n💻 System Resources:")
    print(f"  CPU:")
    print(f"    Average: {df['cpu_percent'].mean():8.1f}%")
    print(f"    Peak:    {df['cpu_percent'].max():8.1f}%")
    print(f"  Memory:")
    print(f"    Average: {df['memory_percent'].mean():8.1f}%")
    print(f"    Peak:    {df['memory_percent'].max():8.1f}%")
    print(f"  Disk:")
    print(f"    Average: {df['disk_percent'].mean():8.1f}%")
    print(f"    Peak:    {df['disk_percent'].max():8.1f}%")
    
    # Bottleneck analysis
    bottlenecks = df[df['bottlenecks'] != '']['bottlenecks'].tolist()
    if bottlenecks:
        print(f"\n⚠️  Bottlenecks Detected: {len(bottlenecks)} times")
        # Count unique bottleneck types
        bottleneck_types = {}
        for b in bottlenecks:
            for bt in str(b).split(';'):
                bt = bt.strip().split(':')[0]
                bottleneck_types[bt] = bottleneck_types.get(bt, 0) + 1
        
        print("  Frequency:")
        for bt, count in sorted(bottleneck_types.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(df)) * 100
            print(f"    {bt:25s}: {count:4d} times ({percentage:5.1f}%)")
    else:
        print(f"\n✅ No bottlenecks detected")
    
    # Capacity estimation
    print(f"\n📈 Capacity Estimates:")
    
    # Find correlation between connections and resources
    if df['rtmp_connections'].max() > 0:
        # Group by number of connections and calculate average CPU/bandwidth
        connection_bins = [0, 10, 20, 30, 40, 50, 75, 100, 150, 200]
        df['connection_bin'] = pd.cut(df['rtmp_connections'], bins=connection_bins)
        grouped = df.groupby('connection_bin').agg({
            'rtmp_connections': 'mean',
            'upload_mbps': 'mean',
            'cpu_percent': 'mean',
            'memory_percent': 'mean'
        }).dropna()
        
        if len(grouped) > 0:
            print(f"\n  Resource Usage by Stream Count:")
            print(f"  {'Streams':<10} {'Upload (Mbps)':<15} {'CPU %':<10} {'Memory %':<10}")
            print(f"  {'-'*10} {'-'*15} {'-'*10} {'-'*10}")
            for idx, row in grouped.iterrows():
                print(f"  {row['rtmp_connections']:>8.0f}   {row['upload_mbps']:>13.2f}   {row['cpu_percent']:>8.1f}   {row['memory_percent']:>10.1f}")
        
        # Estimate capacity based on bottlenecks
        cpu_limit = (80 / df['cpu_percent'].max() * df['rtmp_connections'].max()) if df['cpu_percent'].max() > 0 else float('inf')
        mem_limit = (85 / df['memory_percent'].max() * df['rtmp_connections'].max()) if df['memory_percent'].max() > 0 else float('inf')
        
        # Assume 1Gbps = 900 Mbps usable
        bw_limit = (900 / df['upload_mbps'].max() * df['rtmp_connections'].max()) if df['upload_mbps'].max() > 0 else float('inf')
        
        print(f"\n  Theoretical Limits (extrapolated):")
        print(f"    Based on CPU (80% threshold):     ~{cpu_limit:.0f} streams")
        print(f"    Based on Memory (85% threshold):  ~{mem_limit:.0f} streams")
        print(f"    Based on Bandwidth (1Gbps):       ~{bw_limit:.0f} streams")
        print(f"    Limiting Factor:                  {min([('CPU', cpu_limit), ('Memory', mem_limit), ('Bandwidth', bw_limit)], key=lambda x: x[1])[0]}")
    
    # Network errors
    total_errors = df['network_errors'].sum()
    if total_errors > 0:
        print(f"\n⚠️  Network Errors: {total_errors} total")
    
    print("\n" + "="*80 + "\n")
    
    return df


def plot_data(df, output_file: str = None):
    """Create plots from monitoring data"""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.figure import Figure
    except ImportError:
        print("❌ matplotlib not installed. Install with: pip install matplotlib")
        return
    
    # Convert timestamp to datetime
    df['datetime'] = pd.to_datetime(df['timestamp'])
    
    # Create figure with subplots
    fig, axes = plt.subplots(4, 1, figsize=(14, 12))
    fig.suptitle('Network Monitoring Report', fontsize=16, fontweight='bold')
    
    # Plot 1: Bandwidth
    ax1 = axes[0]
    ax1.plot(df['elapsed_seconds'], df['upload_mbps'], label='Upload', linewidth=2, color='#2E86AB')
    ax1.plot(df['elapsed_seconds'], df['download_mbps'], label='Download', linewidth=2, color='#A23B72')
    ax1.set_ylabel('Bandwidth (Mbps)', fontsize=11, fontweight='bold')
    ax1.set_title('Network Bandwidth', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(left=0)
    
    # Plot 2: Connections
    ax2 = axes[1]
    ax2.plot(df['elapsed_seconds'], df['established_connections'], 
             label='Established', linewidth=2, color='#06A77D')
    ax2.plot(df['elapsed_seconds'], df['rtmp_connections'], 
             label='RTMP', linewidth=2, color='#F18F01', linestyle='--')
    ax2.set_ylabel('Connections', fontsize=11, fontweight='bold')
    ax2.set_title('Active Connections', fontsize=12, fontweight='bold')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(left=0)
    
    # Plot 3: CPU and Memory
    ax3 = axes[2]
    ax3.plot(df['elapsed_seconds'], df['cpu_percent'], 
             label='CPU', linewidth=2, color='#D62828')
    ax3.plot(df['elapsed_seconds'], df['memory_percent'], 
             label='Memory', linewidth=2, color='#F77F00')
    ax3.axhline(y=80, color='red', linestyle=':', alpha=0.5, label='CPU Threshold (80%)')
    ax3.axhline(y=85, color='orange', linestyle=':', alpha=0.5, label='Memory Threshold (85%)')
    ax3.set_ylabel('Usage (%)', fontsize=11, fontweight='bold')
    ax3.set_title('System Resources', fontsize=12, fontweight='bold')
    ax3.legend(loc='upper left')
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim(left=0)
    ax3.set_ylim(0, 100)
    
    # Plot 4: Disk I/O
    ax4 = axes[3]
    ax4.plot(df['elapsed_seconds'], df['disk_read_mbps'], 
             label='Disk Read', linewidth=2, color='#3A86FF')
    ax4.plot(df['elapsed_seconds'], df['disk_write_mbps'], 
             label='Disk Write', linewidth=2, color='#8338EC')
    ax4.set_xlabel('Time (seconds)', fontsize=11, fontweight='bold')
    ax4.set_ylabel('Disk I/O (MB/s)', fontsize=11, fontweight='bold')
    ax4.set_title('Disk I/O', fontsize=12, fontweight='bold')
    ax4.legend(loc='upper left')
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim(left=0)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"📊 Plot saved to: {output_file}")
    else:
        plt.show()


def compare_tests(csv_files: list):
    """Compare multiple test runs"""
    print("="*80)
    print("COMPARISON: Multiple Test Runs")
    print("="*80 + "\n")
    
    results = []
    
    for csv_file in csv_files:
        if not os.path.exists(csv_file):
            print(f"⚠️  Skipping: {csv_file} (not found)")
            continue
        
        try:
            df = pd.read_csv(csv_file)
            results.append({
                'file': os.path.basename(csv_file),
                'duration': df['elapsed_seconds'].max(),
                'max_upload': df['upload_mbps'].max(),
                'avg_upload': df['upload_mbps'].mean(),
                'max_connections': df['established_connections'].max(),
                'avg_connections': df['established_connections'].mean(),
                'max_rtmp': df['rtmp_connections'].max(),
                'max_cpu': df['cpu_percent'].max(),
                'avg_cpu': df['cpu_percent'].mean(),
                'max_memory': df['memory_percent'].max(),
                'bottlenecks': len(df[df['bottlenecks'] != ''])
            })
        except Exception as e:
            print(f"⚠️  Error reading {csv_file}: {e}")
    
    if not results:
        print("❌ No valid test files found")
        return
    
    # Print comparison table
    print(f"{'Test':<40} {'Duration':<10} {'Max Streams':<12} {'Max Upload':<12} {'Max CPU':<10}")
    print(f"{'-'*40} {'-'*10} {'-'*12} {'-'*12} {'-'*10}")
    
    for r in results:
        print(f"{r['file'][:38]:<40} {r['duration']/60:>8.1f}m  {r['max_rtmp']:>10.0f}  {r['max_upload']:>10.2f}  {r['max_cpu']:>8.1f}%")
    
    print("\n📊 Summary:")
    print(f"  Best Stream Count: {max(r['max_rtmp'] for r in results):.0f} ({[r['file'] for r in results if r['max_rtmp'] == max(r['max_rtmp'] for r in results)][0]})")
    print(f"  Best Bandwidth:    {max(r['max_upload'] for r in results):.2f} Mbps ({[r['file'] for r in results if r['max_upload'] == max(r['max_upload'] for r in results)][0]})")
    print(f"  Lowest CPU:        {min(r['max_cpu'] for r in results):.1f}% ({[r['file'] for r in results if r['max_cpu'] == min(r['max_cpu'] for r in results)][0]})")
    
    print("="*80 + "\n")


def find_latest_csv(log_dir: str = "./monitoring-logs"):
    """Find the most recent CSV file"""
    pattern = os.path.join(log_dir, "network_monitor_*.csv")
    files = glob.glob(pattern)
    
    if not files:
        return None
    
    # Sort by modification time
    latest = max(files, key=os.path.getmtime)
    return latest


def main():
    parser = argparse.ArgumentParser(
        description="Analyze network monitoring data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze latest test
  python analyze_monitoring_data.py --latest
  
  # Analyze specific file
  python analyze_monitoring_data.py --file ./monitoring-logs/network_monitor_20231114-120000.csv
  
  # Generate plot
  python analyze_monitoring_data.py --latest --plot
  
  # Compare multiple tests
  python analyze_monitoring_data.py --compare ./monitoring-logs/*.csv
  
  # Save plot to file
  python analyze_monitoring_data.py --latest --plot --output report.png
        """
    )
    
    parser.add_argument(
        '--file', '-f',
        type=str,
        help='Path to CSV file to analyze'
    )
    
    parser.add_argument(
        '--latest', '-l',
        action='store_true',
        help='Analyze the most recent CSV file'
    )
    
    parser.add_argument(
        '--log-dir',
        type=str,
        default='./monitoring-logs',
        help='Directory containing log files (default: ./monitoring-logs)'
    )
    
    parser.add_argument(
        '--plot', '-p',
        action='store_true',
        help='Generate plots (requires matplotlib)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file for plot (default: show plot)'
    )
    
    parser.add_argument(
        '--compare', '-c',
        nargs='+',
        help='Compare multiple CSV files'
    )
    
    args = parser.parse_args()
    
    # Handle comparison mode
    if args.compare:
        compare_tests(args.compare)
        return
    
    # Determine which file to analyze
    csv_file = None
    
    if args.latest:
        csv_file = find_latest_csv(args.log_dir)
        if not csv_file:
            print(f"❌ No monitoring logs found in {args.log_dir}")
            sys.exit(1)
        print(f"📂 Using latest file: {csv_file}\n")
    elif args.file:
        csv_file = args.file
    else:
        # Try to find latest
        csv_file = find_latest_csv(args.log_dir)
        if csv_file:
            print(f"📂 Using latest file: {csv_file}")
            print("   (use --file to specify a different file)\n")
        else:
            print("❌ No CSV file specified and no logs found")
            print("   Use --file or --latest")
            sys.exit(1)
    
    # Analyze
    df = analyze_csv(csv_file)
    
    # Plot if requested
    if args.plot and df is not None:
        plot_data(df, args.output)


if __name__ == '__main__':
    main()

