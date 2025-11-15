#!/usr/bin/env python3
"""
Network and System Monitor for Streaming Capacity Testing
Monitors network bandwidth, connections, and system resources to identify bottlenecks.
"""

import psutil
import time
import csv
import argparse
import sys
import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple
import json

class NetworkMonitor:
    def __init__(self, log_dir: str = "./monitoring-logs", interval: int = 5):
        self.log_dir = log_dir
        self.interval = interval
        self.start_time = time.time()
        self.baseline_net_io = None
        self.baseline_disk_io = None
        
        # Create log directory
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Setup CSV logging
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.csv_file = os.path.join(self.log_dir, f"network_monitor_{timestamp}.csv")
        self.summary_file = os.path.join(self.log_dir, f"network_summary_{timestamp}.txt")
        
        # Initialize metrics storage
        self.metrics_history = []
        self.peak_metrics = {
            'bandwidth_upload_mbps': 0,
            'bandwidth_download_mbps': 0,
            'concurrent_connections': 0,
            'cpu_percent': 0,
            'memory_percent': 0
        }
        
    def get_network_stats(self) -> Dict:
        """Get current network statistics"""
        net_io = psutil.net_io_counters()
        
        # Calculate bandwidth since last check
        if self.baseline_net_io:
            time_delta = self.interval
            bytes_sent = net_io.bytes_sent - self.baseline_net_io.bytes_sent
            bytes_recv = net_io.bytes_recv - self.baseline_net_io.bytes_recv
            
            # Convert to Mbps
            upload_mbps = (bytes_sent * 8) / (time_delta * 1_000_000)
            download_mbps = (bytes_recv * 8) / (time_delta * 1_000_000)
        else:
            upload_mbps = 0
            download_mbps = 0
        
        self.baseline_net_io = net_io
        
        return {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv,
            'errin': net_io.errin,
            'errout': net_io.errout,
            'dropin': net_io.dropin,
            'dropout': net_io.dropout,
            'upload_mbps': upload_mbps,
            'download_mbps': download_mbps
        }
    
    def get_connection_stats(self) -> Dict:
        """Get active network connections statistics"""
        connections = psutil.net_connections(kind='inet')
        
        stats = {
            'total': len(connections),
            'established': 0,
            'listen': 0,
            'time_wait': 0,
            'close_wait': 0,
            'rtmp_connections': 0,
            'http_connections': 0,
            'by_port': defaultdict(int)
        }
        
        for conn in connections:
            # Count by status
            if conn.status == 'ESTABLISHED':
                stats['established'] += 1
            elif conn.status == 'LISTEN':
                stats['listen'] += 1
            elif conn.status == 'TIME_WAIT':
                stats['time_wait'] += 1
            elif conn.status == 'CLOSE_WAIT':
                stats['close_wait'] += 1
            
            # Count by port (local port)
            if conn.laddr:
                port = conn.laddr.port
                stats['by_port'][port] += 1
                
                # Streaming-specific ports
                if port == 1935:  # RTMP
                    stats['rtmp_connections'] += 1
                elif port in [80, 443, 8080]:  # HTTP/HTTPS
                    stats['http_connections'] += 1
        
        return stats
    
    def get_system_stats(self) -> Dict:
        """Get system resource statistics"""
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Disk I/O
        disk_io = psutil.disk_io_counters()
        if self.baseline_disk_io:
            time_delta = self.interval
            read_mb = (disk_io.read_bytes - self.baseline_disk_io.read_bytes) / (1024 * 1024)
            write_mb = (disk_io.write_bytes - self.baseline_disk_io.write_bytes) / (1024 * 1024)
            read_mbps = read_mb / time_delta
            write_mbps = write_mb / time_delta
        else:
            read_mbps = 0
            write_mbps = 0
        
        self.baseline_disk_io = disk_io
        
        return {
            'cpu_percent': cpu_percent,
            'cpu_cores': len(cpu_per_core),
            'cpu_per_core': cpu_per_core,
            'memory_total_gb': memory.total / (1024**3),
            'memory_used_gb': memory.used / (1024**3),
            'memory_percent': memory.percent,
            'disk_total_gb': disk.total / (1024**3),
            'disk_used_gb': disk.used / (1024**3),
            'disk_percent': disk.percent,
            'disk_read_mbps': read_mbps,
            'disk_write_mbps': write_mbps
        }
    
    def get_streaming_processes(self) -> List[Dict]:
        """Get information about streaming-related processes"""
        streaming_keywords = ['ffmpeg', 'obs', 'srs', 'nginx', 'python']
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'num_threads']):
            try:
                pinfo = proc.info
                if any(keyword in pinfo['name'].lower() for keyword in streaming_keywords):
                    processes.append({
                        'pid': pinfo['pid'],
                        'name': pinfo['name'],
                        'cpu_percent': pinfo['cpu_percent'] or 0,
                        'memory_percent': pinfo['memory_percent'] or 0,
                        'num_threads': pinfo['num_threads'] or 0
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return processes
    
    def detect_bottlenecks(self, metrics: Dict) -> List[str]:
        """Detect potential bottlenecks based on current metrics"""
        bottlenecks = []
        
        # CPU bottleneck (>80%)
        if metrics['system']['cpu_percent'] > 80:
            bottlenecks.append(f"HIGH CPU: {metrics['system']['cpu_percent']:.1f}%")
        
        # Memory bottleneck (>85%)
        if metrics['system']['memory_percent'] > 85:
            bottlenecks.append(f"HIGH MEMORY: {metrics['system']['memory_percent']:.1f}%")
        
        # Disk bottleneck (>90%)
        if metrics['system']['disk_percent'] > 90:
            bottlenecks.append(f"HIGH DISK USAGE: {metrics['system']['disk_percent']:.1f}%")
        
        # Network errors
        if metrics['network']['errout'] > 0 or metrics['network']['dropout'] > 0:
            bottlenecks.append(f"NETWORK ERRORS: errout={metrics['network']['errout']}, dropout={metrics['network']['dropout']}")
        
        # High TIME_WAIT connections (may indicate connection exhaustion)
        if metrics['connections']['time_wait'] > 1000:
            bottlenecks.append(f"HIGH TIME_WAIT: {metrics['connections']['time_wait']} connections")
        
        return bottlenecks
    
    def print_metrics(self, metrics: Dict, bottlenecks: List[str]):
        """Print current metrics to console"""
        elapsed = time.time() - self.start_time
        
        print("\n" + "="*80)
        print(f"Monitoring Report - Elapsed Time: {elapsed:.0f}s")
        print("="*80)
        
        # Network
        print("\n📡 NETWORK:")
        print(f"  Upload:   {metrics['network']['upload_mbps']:8.2f} Mbps")
        print(f"  Download: {metrics['network']['download_mbps']:8.2f} Mbps")
        print(f"  Errors:   Out={metrics['network']['errout']}, In={metrics['network']['errin']}")
        print(f"  Drops:    Out={metrics['network']['dropout']}, In={metrics['network']['dropin']}")
        
        # Connections
        print("\n🔌 CONNECTIONS:")
        print(f"  Total:        {metrics['connections']['total']}")
        print(f"  Established:  {metrics['connections']['established']}")
        print(f"  RTMP (1935):  {metrics['connections']['rtmp_connections']}")
        print(f"  HTTP:         {metrics['connections']['http_connections']}")
        print(f"  TIME_WAIT:    {metrics['connections']['time_wait']}")
        
        # System
        print("\n💻 SYSTEM:")
        print(f"  CPU:     {metrics['system']['cpu_percent']:6.1f}%")
        print(f"  Memory:  {metrics['system']['memory_percent']:6.1f}% ({metrics['system']['memory_used_gb']:.1f}/{metrics['system']['memory_total_gb']:.1f} GB)")
        print(f"  Disk:    {metrics['system']['disk_percent']:6.1f}% ({metrics['system']['disk_used_gb']:.1f}/{metrics['system']['disk_total_gb']:.1f} GB)")
        print(f"  Disk I/O: R={metrics['system']['disk_read_mbps']:.2f} MB/s, W={metrics['system']['disk_write_mbps']:.2f} MB/s")
        
        # Streaming processes
        if metrics['processes']:
            print("\n🎥 STREAMING PROCESSES:")
            for proc in metrics['processes'][:10]:  # Top 10
                print(f"  {proc['name']:15s} (PID {proc['pid']:6d}): CPU={proc['cpu_percent']:5.1f}% MEM={proc['memory_percent']:5.1f}% Threads={proc['num_threads']}")
        
        # Bottlenecks
        if bottlenecks:
            print("\n⚠️  BOTTLENECKS DETECTED:")
            for bottleneck in bottlenecks:
                print(f"  • {bottleneck}")
        else:
            print("\n✅ No bottlenecks detected")
        
        # Peak metrics
        print("\n📊 PEAK METRICS (since start):")
        print(f"  Max Upload:      {self.peak_metrics['bandwidth_upload_mbps']:.2f} Mbps")
        print(f"  Max Download:    {self.peak_metrics['bandwidth_download_mbps']:.2f} Mbps")
        print(f"  Max Connections: {self.peak_metrics['concurrent_connections']}")
        print(f"  Max CPU:         {self.peak_metrics['cpu_percent']:.1f}%")
        print(f"  Max Memory:      {self.peak_metrics['memory_percent']:.1f}%")
        
        print("="*80)
    
    def update_peaks(self, metrics: Dict):
        """Update peak metrics"""
        self.peak_metrics['bandwidth_upload_mbps'] = max(
            self.peak_metrics['bandwidth_upload_mbps'],
            metrics['network']['upload_mbps']
        )
        self.peak_metrics['bandwidth_download_mbps'] = max(
            self.peak_metrics['bandwidth_download_mbps'],
            metrics['network']['download_mbps']
        )
        self.peak_metrics['concurrent_connections'] = max(
            self.peak_metrics['concurrent_connections'],
            metrics['connections']['established']
        )
        self.peak_metrics['cpu_percent'] = max(
            self.peak_metrics['cpu_percent'],
            metrics['system']['cpu_percent']
        )
        self.peak_metrics['memory_percent'] = max(
            self.peak_metrics['memory_percent'],
            metrics['system']['memory_percent']
        )
    
    def write_csv_header(self):
        """Write CSV header"""
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp',
                'elapsed_seconds',
                'upload_mbps',
                'download_mbps',
                'network_errors',
                'network_drops',
                'total_connections',
                'established_connections',
                'rtmp_connections',
                'http_connections',
                'time_wait_connections',
                'cpu_percent',
                'memory_percent',
                'disk_percent',
                'disk_read_mbps',
                'disk_write_mbps',
                'bottlenecks'
            ])
    
    def write_csv_row(self, metrics: Dict, bottlenecks: List[str]):
        """Write metrics to CSV"""
        elapsed = time.time() - self.start_time
        
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                f"{elapsed:.1f}",
                f"{metrics['network']['upload_mbps']:.2f}",
                f"{metrics['network']['download_mbps']:.2f}",
                metrics['network']['errout'] + metrics['network']['errin'],
                metrics['network']['dropout'] + metrics['network']['dropin'],
                metrics['connections']['total'],
                metrics['connections']['established'],
                metrics['connections']['rtmp_connections'],
                metrics['connections']['http_connections'],
                metrics['connections']['time_wait'],
                f"{metrics['system']['cpu_percent']:.1f}",
                f"{metrics['system']['memory_percent']:.1f}",
                f"{metrics['system']['disk_percent']:.1f}",
                f"{metrics['system']['disk_read_mbps']:.2f}",
                f"{metrics['system']['disk_write_mbps']:.2f}",
                '; '.join(bottlenecks) if bottlenecks else ''
            ])
    
    def write_summary(self):
        """Write summary report"""
        elapsed = time.time() - self.start_time
        
        with open(self.summary_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("STREAMING CAPACITY MONITORING SUMMARY\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Test Duration: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)\n")
            f.write(f"Samples Collected: {len(self.metrics_history)}\n\n")
            
            f.write("PEAK METRICS:\n")
            f.write("-"*40 + "\n")
            f.write(f"Max Upload Bandwidth:    {self.peak_metrics['bandwidth_upload_mbps']:8.2f} Mbps\n")
            f.write(f"Max Download Bandwidth:  {self.peak_metrics['bandwidth_download_mbps']:8.2f} Mbps\n")
            f.write(f"Max Concurrent Connections: {self.peak_metrics['concurrent_connections']}\n")
            f.write(f"Max CPU Usage:           {self.peak_metrics['cpu_percent']:8.1f}%\n")
            f.write(f"Max Memory Usage:        {self.peak_metrics['memory_percent']:8.1f}%\n\n")
            
            # Calculate averages
            if self.metrics_history:
                avg_upload = sum(m['network']['upload_mbps'] for m in self.metrics_history) / len(self.metrics_history)
                avg_download = sum(m['network']['download_mbps'] for m in self.metrics_history) / len(self.metrics_history)
                avg_connections = sum(m['connections']['established'] for m in self.metrics_history) / len(self.metrics_history)
                avg_cpu = sum(m['system']['cpu_percent'] for m in self.metrics_history) / len(self.metrics_history)
                avg_memory = sum(m['system']['memory_percent'] for m in self.metrics_history) / len(self.metrics_history)
                
                f.write("AVERAGE METRICS:\n")
                f.write("-"*40 + "\n")
                f.write(f"Avg Upload Bandwidth:    {avg_upload:8.2f} Mbps\n")
                f.write(f"Avg Download Bandwidth:  {avg_download:8.2f} Mbps\n")
                f.write(f"Avg Concurrent Connections: {avg_connections:8.1f}\n")
                f.write(f"Avg CPU Usage:           {avg_cpu:8.1f}%\n")
                f.write(f"Avg Memory Usage:        {avg_memory:8.1f}%\n\n")
            
            # Bottleneck analysis
            bottleneck_count = defaultdict(int)
            for metrics in self.metrics_history:
                bottlenecks = self.detect_bottlenecks(metrics)
                for b in bottlenecks:
                    bottleneck_count[b.split(':')[0]] += 1
            
            if bottleneck_count:
                f.write("BOTTLENECK FREQUENCY:\n")
                f.write("-"*40 + "\n")
                for bottleneck, count in sorted(bottleneck_count.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / len(self.metrics_history)) * 100
                    f.write(f"{bottleneck:25s}: {count:4d} times ({percentage:5.1f}%)\n")
                f.write("\n")
            
            # Recommendations
            f.write("RECOMMENDATIONS:\n")
            f.write("-"*40 + "\n")
            
            if self.peak_metrics['cpu_percent'] > 80:
                f.write("⚠️  CPU reached critical levels. Consider:\n")
                f.write("   - Upgrading CPU\n")
                f.write("   - Optimizing encoding settings\n")
                f.write("   - Distributing load across multiple machines\n\n")
            
            if self.peak_metrics['memory_percent'] > 85:
                f.write("⚠️  Memory usage is high. Consider:\n")
                f.write("   - Adding more RAM\n")
                f.write("   - Optimizing buffer sizes\n")
                f.write("   - Checking for memory leaks\n\n")
            
            if self.peak_metrics['bandwidth_upload_mbps'] > 800:  # Assuming 1Gbps = ~900Mbps usable
                f.write("⚠️  Network bandwidth approaching limits. Consider:\n")
                f.write("   - Upgrading network connection\n")
                f.write("   - Reducing stream bitrates\n")
                f.write("   - Using multiple network interfaces\n\n")
            
            f.write(f"\nDetailed logs saved to: {self.csv_file}\n")
            f.write("="*80 + "\n")
        
        print(f"\n📄 Summary report saved to: {self.summary_file}")
    
    def run(self, duration: int = None):
        """Run the monitoring loop"""
        print("🚀 Starting network monitoring...")
        print(f"📁 Logs will be saved to: {self.log_dir}")
        print(f"⏱️  Monitoring interval: {self.interval} seconds")
        if duration:
            print(f"⏰ Will run for: {duration} seconds ({duration/60:.1f} minutes)")
        else:
            print("⏰ Will run until stopped (Ctrl+C)")
        print("\n" + "="*80)
        
        self.write_csv_header()
        
        try:
            iteration = 0
            while True:
                if duration and (time.time() - self.start_time) >= duration:
                    print("\n⏰ Duration reached, stopping monitoring...")
                    break
                
                # Collect metrics
                metrics = {
                    'network': self.get_network_stats(),
                    'connections': self.get_connection_stats(),
                    'system': self.get_system_stats(),
                    'processes': self.get_streaming_processes()
                }
                
                # Store in history
                self.metrics_history.append(metrics)
                
                # Update peaks
                self.update_peaks(metrics)
                
                # Detect bottlenecks
                bottlenecks = self.detect_bottlenecks(metrics)
                
                # Output
                self.print_metrics(metrics, bottlenecks)
                self.write_csv_row(metrics, bottlenecks)
                
                iteration += 1
                
                # Wait for next iteration
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")
        
        # Write summary
        self.write_summary()
        
        print(f"\n✅ Monitoring complete!")
        print(f"📊 {len(self.metrics_history)} samples collected")
        print(f"📁 Data saved to: {self.csv_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Network and System Monitor for Streaming Capacity Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor indefinitely (stop with Ctrl+C)
  python network_monitor.py
  
  # Monitor for 5 minutes
  python network_monitor.py --duration 300
  
  # Monitor with custom interval and log directory
  python network_monitor.py --interval 2 --log-dir /tmp/monitoring
  
  # Run during load testing to find bottlenecks
  python network_monitor.py --duration 600
        """
    )
    
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=5,
        help='Monitoring interval in seconds (default: 5)'
    )
    
    parser.add_argument(
        '--duration', '-d',
        type=int,
        help='Duration to run in seconds (default: run until stopped)'
    )
    
    parser.add_argument(
        '--log-dir', '-l',
        type=str,
        default='./monitoring-logs',
        help='Directory to save logs (default: ./monitoring-logs)'
    )
    
    args = parser.parse_args()
    
    monitor = NetworkMonitor(log_dir=args.log_dir, interval=args.interval)
    monitor.run(duration=args.duration)


if __name__ == '__main__':
    main()

