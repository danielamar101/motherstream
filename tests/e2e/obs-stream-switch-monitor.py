#!/usr/bin/env python3
"""
OBS Stream Switch Monitor
Monitors GMOTHERSTREAM source during stream switches to diagnose timing issues.

This script polls OBS WebSocket to track:
- Media source state changes (PLAYING, BUFFERING, STOPPED, etc.)
- Source visibility changes (hidden/visible)
- Timing between restart triggers and actual readiness

Purpose: Verify if GMOTHERSTREAM becomes visible before it's fully initialized,
causing frozen frames during stream switches.
"""

import os
import sys
import time
import csv
import signal
from datetime import datetime
from obswebsocket import obsws, requests as obs_requests
from websocket import WebSocketConnectionClosedException

# Configuration
DEFAULT_POLL_INTERVAL = 0.2  # 200ms - can be adjusted via CLI
SOURCE_NAME = "GMOTHERSTREAM"
SCENE_NAME = "MOTHERSTREAM"

class OBSMonitor:
    def __init__(self, output_file, poll_interval=DEFAULT_POLL_INTERVAL):
        self.output_file = output_file
        self.poll_interval = poll_interval
        self.source_name = SOURCE_NAME
        self.scene_name = SCENE_NAME
        
        # OBS connection
        self.obs_host = os.environ.get("OBS_HOST", "localhost")
        self.obs_port = int(os.environ.get("OBS_PORT", 4455))
        self.obs_password = os.environ.get("OBS_PASSWORD")
        self.ws = None
        
        # State tracking
        self.prev_visible = None
        self.prev_media_state = None
        self.prev_scene_item_id = None
        
        # Statistics
        self.state_changes = []
        self.poll_count = 0
        self.error_count = 0
        self.problematic_transitions = []
        
        # CSV writer
        self.csv_file = None
        self.csv_writer = None
        
        # Running flag
        self.running = True
        
    def connect_obs(self):
        """Connect to OBS WebSocket"""
        try:
            print(f"Connecting to OBS at {self.obs_host}:{self.obs_port}...")
            self.ws = obsws(self.obs_host, self.obs_port, self.obs_password)
            self.ws.connect()
            print("✓ Connected to OBS WebSocket")
            
            # Test the connection
            version = self.ws.call(obs_requests.GetVersion())
            print(f"✓ OBS Studio version: {version.datain.get('obsVersion', 'unknown')}")
            print(f"✓ OBS WebSocket version: {version.datain.get('obsWebSocketVersion', 'unknown')}")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to OBS: {e}")
            return False
    
    def disconnect_obs(self):
        """Disconnect from OBS WebSocket"""
        if self.ws:
            try:
                self.ws.disconnect()
                print("✓ Disconnected from OBS WebSocket")
            except:
                pass
    
    def get_scene_item_id(self):
        """Get the scene item ID for GMOTHERSTREAM"""
        try:
            scene_items = self.ws.call(obs_requests.GetSceneItemList(sceneName=self.scene_name))
            for item in scene_items.datain.get('sceneItems', []):
                if item.get('sourceName') == self.source_name:
                    return item.get('sceneItemId')
            return None
        except Exception as e:
            return None
    
    def get_source_visibility(self):
        """Get current visibility of GMOTHERSTREAM"""
        try:
            if self.prev_scene_item_id is None:
                self.prev_scene_item_id = self.get_scene_item_id()
                if self.prev_scene_item_id is None:
                    return None
            
            response = self.ws.call(
                obs_requests.GetSceneItemEnabled(
                    sceneName=self.scene_name,
                    sceneItemId=self.prev_scene_item_id
                )
            )
            return response.datain.get('sceneItemEnabled', False)
        except Exception as e:
            return None
    
    def get_media_status(self):
        """Get current media state of GMOTHERSTREAM"""
        try:
            response = self.ws.call(obs_requests.GetMediaInputStatus(inputName=self.source_name))
            return response.datain.get('mediaState', 'UNKNOWN')
        except Exception as e:
            return None
    
    def init_csv(self):
        """Initialize CSV output file"""
        try:
            # Ensure the directory exists
            output_dir = os.path.dirname(self.output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                print(f"✓ Created directory: {output_dir}")
            
            self.csv_file = open(self.output_file, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            
            # Write header
            self.csv_writer.writerow([
                'Timestamp',
                'Timestamp_Float',
                'Poll_Count',
                'Event_Type',
                'Visibility',
                'Media_State',
                'Notes'
            ])
            self.csv_file.flush()
            print(f"✓ CSV output: {self.output_file}")
        except Exception as e:
            print(f"✗ Failed to create CSV file: {e}")
            print(f"   Output path: {self.output_file}")
            print(f"   Current directory: {os.getcwd()}")
            sys.exit(1)
    
    def log_event(self, event_type, visibility, media_state, notes=""):
        """Log an event to CSV"""
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        timestamp_float = time.time()
        
        self.csv_writer.writerow([
            timestamp_str,
            f"{timestamp_float:.3f}",
            self.poll_count,
            event_type,
            visibility,
            media_state,
            notes
        ])
        self.csv_file.flush()
        
        # Store for analysis
        self.state_changes.append({
            'timestamp': timestamp_float,
            'event_type': event_type,
            'visibility': visibility,
            'media_state': media_state,
            'notes': notes
        })
    
    def detect_problem(self, visibility, media_state):
        """Detect problematic state transitions"""
        # Problem: Source is visible but media is not PLAYING
        if visibility and media_state and media_state != 'UNKNOWN':
            if 'PLAYING' not in media_state.upper():
                return f"⚠️ PROBLEM: Source visible while in {media_state} state!"
        return ""
    
    def poll_once(self):
        """Perform one poll of OBS state"""
        try:
            visibility = self.get_source_visibility()
            media_state = self.get_media_status()
            
            self.poll_count += 1
            
            # Detect state changes
            visibility_changed = visibility != self.prev_visible
            media_state_changed = media_state != self.prev_media_state
            
            if visibility_changed or media_state_changed:
                # Determine event type
                event_type = "STATE_CHANGE"
                if visibility_changed and media_state_changed:
                    event_type = "COMBINED_CHANGE"
                elif visibility_changed:
                    event_type = "VISIBILITY_CHANGE"
                elif media_state_changed:
                    event_type = "MEDIA_STATE_CHANGE"
                
                # Check for problems
                problem_note = self.detect_problem(visibility, media_state)
                
                # Build detailed notes
                notes_parts = []
                if visibility_changed:
                    old_vis = "visible" if self.prev_visible else "hidden"
                    new_vis = "visible" if visibility else "hidden"
                    notes_parts.append(f"Visibility: {old_vis} → {new_vis}")
                if media_state_changed:
                    notes_parts.append(f"MediaState: {self.prev_media_state} → {media_state}")
                if problem_note:
                    notes_parts.append(problem_note)
                    self.problematic_transitions.append({
                        'timestamp': time.time(),
                        'visibility': visibility,
                        'media_state': media_state,
                        'note': problem_note
                    })
                
                notes = "; ".join(notes_parts)
                
                # Log to CSV
                self.log_event(event_type, visibility, media_state, notes)
                
                # Print to console
                timestamp_str = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                vis_str = "👁 VISIBLE" if visibility else "🙈 HIDDEN"
                state_str = f"📺 {media_state}" if media_state else "📺 UNKNOWN"
                
                color = ""
                if problem_note:
                    color = "\033[91m"  # Red
                elif "PLAYING" in str(media_state):
                    color = "\033[92m"  # Green
                else:
                    color = "\033[93m"  # Yellow
                
                print(f"{color}[{timestamp_str}] {event_type:20s} | {vis_str:12s} | {state_str:25s} | {notes}\033[0m")
                
                # Update previous state
                self.prev_visible = visibility
                self.prev_media_state = media_state
            
            return True
            
        except WebSocketConnectionClosedException:
            self.error_count += 1
            print(f"\n⚠️ WebSocket connection closed. Attempting to reconnect...")
            time.sleep(2)
            if self.connect_obs():
                print("✓ Reconnected successfully")
                # Reset scene item ID
                self.prev_scene_item_id = None
                return True
            else:
                print("✗ Reconnection failed")
                return False
        except Exception as e:
            self.error_count += 1
            if self.error_count % 10 == 0:  # Only print every 10th error to avoid spam
                print(f"⚠️ Poll error: {e}")
            return True
    
    def poll_loop(self):
        """Main polling loop"""
        print(f"\n{'='*80}")
        print(f"Starting OBS monitoring (poll interval: {self.poll_interval*1000:.0f}ms)")
        print(f"Watching: {self.source_name} in scene {self.scene_name}")
        print(f"Press Ctrl+C to stop and generate report")
        print(f"{'='*80}\n")
        
        try:
            # Get initial state
            self.prev_visible = self.get_source_visibility()
            self.prev_media_state = self.get_media_status()
            
            if self.prev_visible is not None and self.prev_media_state is not None:
                vis_str = "visible" if self.prev_visible else "hidden"
                print(f"Initial state: {vis_str}, {self.prev_media_state}\n")
                self.log_event("INITIAL_STATE", self.prev_visible, self.prev_media_state, "Monitoring started")
            else:
                print("⚠️ Could not get initial state. Source may not exist.\n")
            
            # Main loop
            while self.running:
                if not self.poll_once():
                    # Connection lost and couldn't reconnect
                    break
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            print("\n\n✓ Monitoring stopped by user")
    
    def generate_report(self):
        """Generate summary report"""
        report_file = self.output_file.replace('.csv', '-report.txt')
        
        try:
            with open(report_file, 'w') as f:
                f.write("="*80 + "\n")
                f.write("OBS Stream Switch Monitoring Report\n")
                f.write("="*80 + "\n\n")
                
                f.write(f"Monitoring Duration: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Source: {self.source_name}\n")
                f.write(f"Scene: {self.scene_name}\n")
                f.write(f"Poll Interval: {self.poll_interval*1000:.0f}ms\n\n")
                
                f.write("="*80 + "\n")
                f.write("Statistics\n")
                f.write("="*80 + "\n\n")
                
                f.write(f"Total Polls: {self.poll_count}\n")
                f.write(f"State Changes Detected: {len(self.state_changes)}\n")
                f.write(f"Problematic Transitions: {len(self.problematic_transitions)}\n")
                f.write(f"Connection Errors: {self.error_count}\n\n")
                
                if self.problematic_transitions:
                    f.write("="*80 + "\n")
                    f.write("⚠️  PROBLEMATIC TRANSITIONS DETECTED\n")
                    f.write("="*80 + "\n\n")
                    
                    f.write("These transitions show the source becoming visible while NOT in PLAYING state:\n\n")
                    
                    for i, problem in enumerate(self.problematic_transitions, 1):
                        timestamp = datetime.fromtimestamp(problem['timestamp']).strftime('%H:%M:%S.%f')[:-3]
                        f.write(f"{i}. [{timestamp}] Visibility={problem['visibility']}, "
                               f"State={problem['media_state']}\n")
                        f.write(f"   {problem['note']}\n\n")
                    
                    f.write("CONCLUSION: Source is becoming visible before it's ready!\n")
                    f.write("This confirms the hypothesis about frozen frames during stream switches.\n\n")
                else:
                    f.write("="*80 + "\n")
                    f.write("✓ NO PROBLEMATIC TRANSITIONS DETECTED\n")
                    f.write("="*80 + "\n\n")
                    
                    f.write("The source only became visible when in PLAYING state.\n")
                    f.write("The hypothesis about premature visibility may be incorrect.\n\n")
                
                if len(self.state_changes) > 1:
                    f.write("="*80 + "\n")
                    f.write("Detailed State Transitions\n")
                    f.write("="*80 + "\n\n")
                    
                    for change in self.state_changes:
                        timestamp = datetime.fromtimestamp(change['timestamp']).strftime('%H:%M:%S.%f')[:-3]
                        vis_str = "VISIBLE" if change['visibility'] else "HIDDEN"
                        f.write(f"[{timestamp}] {change['event_type']:20s} | {vis_str:8s} | "
                               f"{change['media_state']:20s} | {change['notes']}\n")
                
                f.write("\n" + "="*80 + "\n")
                f.write("End of Report\n")
                f.write("="*80 + "\n")
            
            print(f"\n✓ Report generated: {report_file}")
            
            # Also print summary to console
            print("\n" + "="*80)
            print("MONITORING SUMMARY")
            print("="*80)
            print(f"Total Polls: {self.poll_count}")
            print(f"State Changes: {len(self.state_changes)}")
            print(f"Problematic Transitions: {len(self.problematic_transitions)}")
            
            if self.problematic_transitions:
                print("\n⚠️  PROBLEMS DETECTED! Source became visible before ready.")
                print(f"See {report_file} for details.")
            else:
                print("\n✓ No problems detected. Source visibility timing looks correct.")
            
            print("="*80 + "\n")
            
        except Exception as e:
            print(f"⚠️ Failed to generate report: {e}")
    
    def run(self):
        """Main run method"""
        # Setup signal handler for graceful shutdown
        def signal_handler(sig, frame):
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Connect to OBS
        if not self.connect_obs():
            print("Failed to connect to OBS. Exiting.")
            sys.exit(1)
        
        # Initialize CSV
        self.init_csv()
        
        try:
            # Run monitoring loop
            self.poll_loop()
        finally:
            # Cleanup
            if self.csv_file:
                self.csv_file.close()
            
            self.disconnect_obs()
            
            # Generate report
            if len(self.state_changes) > 0:
                self.generate_report()
            else:
                print("\nNo state changes detected during monitoring.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Monitor OBS source state during stream switches',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor with default settings (200ms poll interval)
  python3 obs-stream-switch-monitor.py
  
  # Monitor with slower polling (500ms) to reduce OBS load
  python3 obs-stream-switch-monitor.py --poll-interval 0.5
  
  # Specify custom output file
  python3 obs-stream-switch-monitor.py --output logs/custom-monitor.csv
  
  # Faster polling (100ms) for high-resolution timing
  python3 obs-stream-switch-monitor.py --poll-interval 0.1

Environment variables (required):
  OBS_HOST       - OBS WebSocket host (default: localhost)
  OBS_PORT       - OBS WebSocket port (default: 4455)
  OBS_PASSWORD   - OBS WebSocket password
        """
    )
    
    # Get the script directory to create logs relative to it
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_output = os.path.join(script_dir, 'logs2', f'obs-monitor-{datetime.now().strftime("%Y%m%d-%H%M%S")}.csv')
    
    parser.add_argument(
        '--output', '-o',
        default=default_output,
        help='Output CSV file path (default: tests/e2e/logs2/obs-monitor-TIMESTAMP.csv)'
    )
    
    parser.add_argument(
        '--poll-interval', '-p',
        type=float,
        default=DEFAULT_POLL_INTERVAL,
        help=f'Poll interval in seconds (default: {DEFAULT_POLL_INTERVAL}s = {DEFAULT_POLL_INTERVAL*1000:.0f}ms)'
    )
    
    args = parser.parse_args()
    
    # Create and run monitor (directory creation is handled in init_csv)
    monitor = OBSMonitor(args.output, args.poll_interval)
    monitor.run()


if __name__ == '__main__':
    main()

