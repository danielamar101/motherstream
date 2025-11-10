#!/bin/bash
# motherstream-stress-test.sh - Comprehensive E2E stress testing for motherstream
# Usage: ./motherstream-stress-test.sh [scenario] [video_file]
#   Scenarios: simultaneous, orderly, chaos, rapid-reconnect, queue-drain, all

set -e

# ==================== Configuration ====================

NUM_USERS=10
SCENARIO=${1:-"orderly"}
TEST_VIDEO=${2:-"videos/test-video.mp4"}
BASE_STREAM_KEY="stress_test_user"
BASE_EMAIL="stresstest"
BASE_DJ_NAME="StressTestDJ"
LOG_DIR="./logs"
RESULTS_FILE="$LOG_DIR/results-$(date +%Y%m%d-%H%M%S).log"
USER_DATA_FILE="$LOG_DIR/test-users.json"

# Video configuration
VIDEO_DIR="videos"
declare -a VIDEOS  # Array to hold video paths

# Server configuration
if [ "${ENV}" = "STAGE" ]; then
    HOST="staging.motherstream.live:1937"
    API_HOST="https://staging.motherstream.live"
else
    HOST="motherstream.live"
    API_HOST="https://motherstream.live"
fi

# Timing configuration
ORDERLY_DURATION=60        # Each user streams for 60 seconds
CHAOS_MIN_DURATION=15      # Minimum stream duration in chaos mode
CHAOS_MAX_DURATION=90      # Maximum stream duration in chaos mode
RECONNECT_INTERVAL=5       # Seconds between reconnect attempts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# ==================== Helper Functions ====================

log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$RESULTS_FILE"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $@" | tee -a "$RESULTS_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $@" | tee -a "$RESULTS_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $@" | tee -a "$RESULTS_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $@" | tee -a "$RESULTS_FILE"
}

log_queue() {
    echo -e "${CYAN}[QUEUE]${NC} $@" | tee -a "$RESULTS_FILE"
}

log_stream() {
    echo -e "${MAGENTA}[STREAM]${NC} $@" | tee -a "$RESULTS_FILE"
}

log_api() {
    echo -e "${GREEN}[API]${NC} $@" | tee -a "$RESULTS_FILE"
}

# Discover available videos
discover_videos() {
    VIDEOS=()
    
    # Find all video files in videos directory
    if [ -d "$VIDEO_DIR" ]; then
        while IFS= read -r -d '' video; do
            VIDEOS+=("$video")
        done < <(find "$VIDEO_DIR" -type f \( -name "*.mp4" -o -name "*.avi" -o -name "*.mkv" -o -name "*.mov" \) -print0 | sort -z)
    fi
    
    if [ ${#VIDEOS[@]} -eq 0 ]; then
        log_error "No video files found in $VIDEO_DIR/"
        log_info "Download videos with:"
        log_info "  ./scripts/download-test-video.sh"
        exit 1
    fi
    
    log_success "Found ${#VIDEOS[@]} video(s)"
    for i in "${!VIDEOS[@]}"; do
        local filename=$(basename "${VIDEOS[$i]}")
        log_info "  Video $((i+1)): $filename"
    done
}

# Get video for specific user (cycles through available videos)
get_video_for_user() {
    local user_id=$1
    local video_index=$((user_id % ${#VIDEOS[@]}))
    echo "${VIDEOS[$video_index]}"
}

# Create test users via API
create_test_users() {
    log_info "========================================="
    log_info "Creating Test Users via API"
    log_info "========================================="
    
    # Clear previous user data
    echo "[]" > "$USER_DATA_FILE"
    
    local created_users=()
    
    for i in $(seq 1 $NUM_USERS); do
        local email="${BASE_EMAIL}${i}@motherstream.test"
        local dj_name="${BASE_DJ_NAME}_${i}"
        local stream_key="${BASE_STREAM_KEY}_${i}"
        local password="TestPass123!${i}"
        
        log_api "Creating user $i: $email / $dj_name"
        
        # Create user via API
        local response=$(curl -s -X POST "$API_HOST/api/users/register" \
            -H "Content-Type: application/json" \
            -d "{
                \"email\": \"$email\",
                \"dj_name\": \"$dj_name\",
                \"password\": \"$password\",
                \"timezone\": \"UTC\"
            }" 2>&1)
        
        local http_code=$(echo "$response" | tail -c 4)
        
        # Check if user was created or already exists
        if echo "$response" | grep -q "stream_key" || echo "$response" | grep -q "already exists"; then
            log_success "✓ User $i ready: $dj_name (key: $stream_key)"
            
            # Store user data
            created_users+=("{\"id\":$i,\"email\":\"$email\",\"dj_name\":\"$dj_name\",\"stream_key\":\"$stream_key\"}")
        else
            log_warning "⚠ Could not create user $i (may need manual setup)"
            log_info "Response: $response"
            
            # Still add to list with expected stream key
            created_users+=("{\"id\":$i,\"email\":\"$email\",\"dj_name\":\"$dj_name\",\"stream_key\":\"$stream_key\"}")
        fi
        
        sleep 0.5  # Rate limit protection
    done
    
    # Save user data to file
    local json_array=$(printf '%s\n' "${created_users[@]}" | jq -s '.')
    echo "$json_array" > "$USER_DATA_FILE"
    
    log_success "Created/verified $NUM_USERS test users"
    log_info "User data saved to: $USER_DATA_FILE"
    echo ""
}

# Clean up test users (optional)
cleanup_test_users() {
    log_info "Note: Test users remain in database for reuse"
    log_info "To manually clean up, delete users with email: ${BASE_EMAIL}*@motherstream.test"
}

# Create log directory
setup_logs() {
    mkdir -p "$LOG_DIR"
    log_info "Logging to: $RESULTS_FILE"
    
    # Clear old user logs
    rm -f "$LOG_DIR"/user*.log "$LOG_DIR"/user*.pid
}

# Start a single user stream
start_stream() {
    local user_id=$1
    local duration=$2
    local delay=${3:-0}
    local stream_key="${BASE_STREAM_KEY}_${user_id}"
    local log_file="$LOG_DIR/user${user_id}.log"
    
    # Get video for this user (cycles through available videos)
    local video_file=$(get_video_for_user $user_id)
    local video_name=$(basename "$video_file")
    
    # Delay start if specified
    if [ $delay -gt 0 ]; then
        sleep $delay
    fi
    
    log_stream "User $user_id starting stream (duration: ${duration}s, video: $video_name, key: $stream_key)"
    
    # Start ffmpeg with timeout using user-specific video
    timeout $duration ffmpeg -re -stream_loop -1 -i "$video_file" \
        -c:v libx264 -preset ultrafast -crf 23 -g 60 \
        -c:a aac -b:a 128k -ar 44100 -ac 2 \
        -f flv "rtmp://$HOST/live/$stream_key?secret=always12" \
        > "$log_file" 2>&1 &
    
    local pid=$!
    echo $pid > "$LOG_DIR/user${user_id}.pid"
    
    # Monitor the stream
    (
        wait $pid
        local exit_code=$?
        if [ $exit_code -eq 0 ] || [ $exit_code -eq 124 ]; then
            log_stream "User $user_id stream ended normally (exit: $exit_code)"
        else
            log_error "User $user_id stream failed (exit: $exit_code)"
        fi
        rm -f "$LOG_DIR/user${user_id}.pid"
    ) &
}

# Stop a user stream
stop_stream() {
    local user_id=$1
    local pid_file="$LOG_DIR/user${user_id}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            log_stream "Stopping user $user_id (PID: $pid)"
            kill $pid 2>/dev/null || true
            sleep 1
            kill -9 $pid 2>/dev/null || true
            rm -f "$pid_file"
        fi
    fi
}

# Get current queue state from API
get_queue_state() {
    curl -s "$API_HOST/api/queue" 2>/dev/null || echo '{"queue":[],"error":"API unavailable"}'
}

# Monitor queue state
monitor_queue() {
    local duration=$1
    local interval=5
    local elapsed=0
    
    log_info "Starting queue monitor (duration: ${duration}s, interval: ${interval}s)"
    
    while [ $elapsed -lt $duration ]; do
        local queue_state=$(get_queue_state)
        
        # Check if jq is available
        if command -v jq &> /dev/null; then
            local queue_length=$(echo "$queue_state" | jq -r '.queue | length' 2>/dev/null || echo "N/A")
            local lead_streamer=$(echo "$queue_state" | jq -r '.queue[0].dj_name' 2>/dev/null || echo "N/A")
            log_queue "Length: $queue_length, Lead: $lead_streamer"
        else
            log_queue "State: $queue_state"
        fi
        
        sleep $interval
        elapsed=$((elapsed + interval))
    done
}

# Count active streams
count_active_streams() {
    local count=0
    for i in $(seq 1 $NUM_USERS); do
        if [ -f "$LOG_DIR/user${i}.pid" ]; then
            local pid=$(cat "$LOG_DIR/user${i}.pid")
            if ps -p $pid > /dev/null 2>&1; then
                count=$((count + 1))
            fi
        fi
    done
    echo $count
}

# Stop all streams
cleanup() {
    log_info "Cleaning up all streams..."
    for i in $(seq 1 $NUM_USERS); do
        stop_stream $i
    done
    
    # Wait for all background jobs
    wait 2>/dev/null || true
    
    log_info "Cleanup complete"
}

# ==================== Test Scenarios ====================

# Scenario 1: All users connect simultaneously
scenario_simultaneous() {
    log_info "========================================="
    log_info "SCENARIO 1: Simultaneous Start"
    log_info "========================================="
    log_info "Testing: Double-start race condition"
    log_info "All $NUM_USERS users will attempt to connect at the exact same time"
    log_info "Expected: Only 1 should forward, ${NUM_USERS} total should be in queue"
    echo ""
    
    # Start queue monitor in background
    monitor_queue 30 &
    local monitor_pid=$!
    
    # Start all users at the same time
    log_info "Launching all users simultaneously..."
    for i in $(seq 1 $NUM_USERS); do
        start_stream $i 25 0 &
    done
    
    # Wait a bit for connections to establish
    sleep 8
    
    # Check queue state
    local queue_state=$(get_queue_state)
    
    if command -v jq &> /dev/null; then
        local queue_length=$(echo "$queue_state" | jq -r '.queue | length' 2>/dev/null || echo "0")
        
        log_info "Queue length after simultaneous start: $queue_length"
        
        if [ "$queue_length" -eq "$NUM_USERS" ]; then
            log_success "✓ All $NUM_USERS users in queue (race condition handled correctly!)"
        elif [ "$queue_length" -gt 0 ]; then
            log_warning "! Queue length is $queue_length, expected $NUM_USERS"
            log_warning "  This might indicate some users failed to connect"
        else
            log_error "✗ Queue appears empty or API unavailable"
        fi
    else
        log_warning "jq not installed, skipping detailed queue check"
    fi
    
    # Wait for streams to finish
    sleep 20
    
    # Stop monitor
    kill $monitor_pid 2>/dev/null || true
    wait $monitor_pid 2>/dev/null || true
    
    cleanup
    echo ""
    log_success "✓ Simultaneous start scenario complete"
    echo ""
}

# Scenario 2: Orderly rotation (each user 1 minute)
scenario_orderly() {
    log_info "========================================="
    log_info "SCENARIO 2: Orderly Queue Rotation"
    log_info "========================================="
    log_info "Testing: switch_stream non-reentrant lock, queue management"
    log_info "Each user streams for exactly ${ORDERLY_DURATION}s before disconnecting"
    log_info "Expected: Smooth transitions, proper queue order maintained"
    echo ""
    
    # Start queue monitor in background
    local total_duration=$((NUM_USERS * ORDERLY_DURATION + 30))
    monitor_queue $total_duration &
    local monitor_pid=$!
    
    log_info "Starting orderly rotation with $NUM_USERS users..."
    
    # Start all users at once with staggered start (0.5s apart to avoid exact collision)
    for i in $(seq 1 $NUM_USERS); do
        local stream_duration=$((total_duration + 10)) # Long enough to cover whole test
        start_stream $i $stream_duration 0 &
        sleep 0.5  # Small stagger
    done
    
    sleep 5  # Let queue build
    log_info "Queue built. Beginning orderly rotation..."
    
    # Disconnect lead every minute to trigger switches
    for i in $(seq 1 $NUM_USERS); do
        log_info "Minute $i: User $i should be lead streamer"
        
        if [ $i -lt $NUM_USERS ]; then
            sleep $ORDERLY_DURATION
            log_info "Disconnecting user $i to trigger switch..."
            stop_stream $i
            sleep 2  # Brief pause for switch to happen
        else
            # Last user - let them finish naturally
            sleep $ORDERLY_DURATION
        fi
    done
    
    # Stop monitor
    kill $monitor_pid 2>/dev/null || true
    wait $monitor_pid 2>/dev/null || true
    
    cleanup
    echo ""
    log_success "✓ Orderly rotation scenario complete"
    echo ""
}

# Scenario 3: Chaos mode (random timings)
scenario_chaos() {
    log_info "========================================="
    log_info "SCENARIO 3: Chaos Mode"
    log_info "========================================="
    log_info "Testing: All race conditions under unpredictable load"
    log_info "Random start times, durations, and reconnects"
    log_info "Expected: System remains stable, no crashes or deadlocks"
    echo ""
    
    # Start queue monitor
    monitor_queue 180 &
    local monitor_pid=$!
    
    # Launch users with random delays and durations
    log_info "Launching chaos with $NUM_USERS users..."
    for i in $(seq 1 $NUM_USERS); do
        local start_delay=$((RANDOM % 30))  # 0-30 seconds
        local duration=$((CHAOS_MIN_DURATION + RANDOM % (CHAOS_MAX_DURATION - CHAOS_MIN_DURATION)))
        
        log_info "User $i: start in ${start_delay}s, duration ${duration}s"
        
        (
            sleep $start_delay
            start_stream $i $duration 0
            
            # 30% chance of immediate reconnect after disconnect
            if [ $((RANDOM % 10)) -lt 3 ]; then
                sleep 3
                log_info "User $i attempting immediate reconnect (chaos!)"
                start_stream $i 30 0
            fi
        ) &
    done
    
    # Let chaos run for 3 minutes
    log_info "Chaos mode running for 180 seconds..."
    sleep 180
    
    # Stop monitor
    kill $monitor_pid 2>/dev/null || true
    wait $monitor_pid 2>/dev/null || true
    
    cleanup
    echo ""
    log_success "✓ Chaos mode scenario complete (survived chaos!)"
    echo ""
}

# Scenario 4: Rapid disconnect/reconnect
scenario_rapid_reconnect() {
    log_info "========================================="
    log_info "SCENARIO 4: Rapid Disconnect/Reconnect"
    log_info "========================================="
    log_info "Testing: Stale reads, duplicate detection, state consistency"
    log_info "Users repeatedly disconnect and reconnect every 10 seconds"
    log_info "Expected: No duplicates in queue, proper state tracking"
    echo ""
    
    # Start queue monitor
    monitor_queue 120 &
    local monitor_pid=$!
    
    # Each user does 5 cycles of connect(10s) -> disconnect -> reconnect
    for cycle in $(seq 1 5); do
        log_info "Cycle $cycle/5: Starting all users..."
        
        for i in $(seq 1 $NUM_USERS); do
            start_stream $i 12 0 &
            sleep 0.1  # Tiny stagger
        done
        
        sleep 10  # Let them stream briefly
        
        local active=$(count_active_streams)
        log_info "Cycle $cycle: Active streams: $active"
        
        log_info "Cycle $cycle: Disconnecting all users..."
        cleanup
        
        sleep 3  # Brief pause before reconnect
    done
    
    # Final check
    sleep 5
    local final_active=$(count_active_streams)
    log_info "Final active streams: $final_active (should be 0)"
    
    # Stop monitor
    kill $monitor_pid 2>/dev/null || true
    wait $monitor_pid 2>/dev/null || true
    
    echo ""
    log_success "✓ Rapid reconnect scenario complete"
    echo ""
}

# Scenario 5: Queue drain (test empty queue handling)
scenario_queue_drain() {
    log_info "========================================="
    log_info "SCENARIO 5: Queue Drain"
    log_info "========================================="
    log_info "Testing: Empty queue handling, OBS shutdown, obs_turned_off flag"
    log_info "Build up queue, then let it gradually empty"
    log_info "Expected: Clean drain to empty, proper OBS state management"
    echo ""
    
    # Start queue monitor
    monitor_queue 150 &
    local monitor_pid=$!
    
    # Phase 1: Build up the queue
    log_info "Phase 1: Building queue with all $NUM_USERS users..."
    for i in $(seq 1 $NUM_USERS); do
        start_stream $i 120 0 &
        sleep 0.5
    done
    
    sleep 10  # Let queue build
    
    local queue_state=$(get_queue_state)
    if command -v jq &> /dev/null; then
        local queue_length=$(echo "$queue_state" | jq -r '.queue | length' 2>/dev/null || echo "N/A")
        log_info "Queue built: $queue_length users"
    fi
    
    # Phase 2: Gradually disconnect users
    log_info "Phase 2: Gradual queue drain (one user every 10-15 seconds)..."
    for i in $(seq 1 $NUM_USERS); do
        local wait_time=$((10 + RANDOM % 6))  # 10-15 seconds apart
        sleep $wait_time
        stop_stream $i
        log_info "Disconnected user $i, $(($NUM_USERS - $i)) remaining"
    done
    
    # Phase 3: Verify queue is empty
    log_info "Phase 3: Verifying empty queue..."
    sleep 10
    
    local queue_state=$(get_queue_state)
    if command -v jq &> /dev/null; then
        local queue_length=$(echo "$queue_state" | jq -r '.queue | length' 2>/dev/null || echo "0")
        
        if [ "$queue_length" -eq "0" ]; then
            log_success "✓ Queue successfully drained to 0"
        else
            log_warning "! Queue length is $queue_length, expected 0"
        fi
    fi
    
    # Stop monitor
    kill $monitor_pid 2>/dev/null || true
    wait $monitor_pid 2>/dev/null || true
    
    cleanup
    echo ""
    log_success "✓ Queue drain scenario complete"
    echo ""
}

# Run all scenarios
scenario_all() {
    log_info "========================================="
    log_info "RUNNING ALL SCENARIOS (COMPREHENSIVE TEST)"
    log_info "========================================="
    log_info "This will take approximately 15-20 minutes"
    echo ""
    
    local start_time=$(date +%s)
    
    scenario_simultaneous
    sleep 5
    
    scenario_orderly
    sleep 5
    
    scenario_rapid_reconnect
    sleep 5
    
    scenario_chaos
    sleep 5
    
    scenario_queue_drain
    
    local end_time=$(date +%s)
    local total_time=$((end_time - start_time))
    local minutes=$((total_time / 60))
    local seconds=$((total_time % 60))
    
    echo ""
    log_success "========================================="
    log_success "ALL SCENARIOS COMPLETE!"
    log_success "Total time: ${minutes}m ${seconds}s"
    log_success "========================================="
}

# ==================== Main ====================

print_banner() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                                                                ║"
    echo "║        🎬 MOTHERSTREAM E2E STRESS TEST 🎬                      ║"
    echo "║                                                                ║"
    echo "║        Comprehensive Real-World Race Condition Testing        ║"
    echo "║                                                                ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
}

print_summary() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                     TEST SCENARIOS AVAILABLE                   ║"
    echo "╠════════════════════════════════════════════════════════════════╣"
    echo "║  simultaneous    - All users connect at once (10s)             ║"
    echo "║  orderly         - Sequential 1-min rotations (10m)            ║"
    echo "║  chaos           - Random timings & reconnects (3m)            ║"
    echo "║  rapid-reconnect - Repeated connect/disconnect (2m)            ║"
    echo "║  queue-drain     - Build & drain queue (3m)                    ║"
    echo "║  all             - Run all scenarios (15-20m)                  ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
}

main() {
    print_banner
    
    log_info "Configuration:"
    log_info "  Scenario: $SCENARIO"
    log_info "  Users: $NUM_USERS"
    log_info "  Host: $HOST"
    log_info "  API: $API_HOST"
    echo ""
    
    # Setup
    setup_logs
    discover_videos
    
    # Create test users via API
    create_test_users
    
    # Check for required tools
    if ! command -v ffmpeg &> /dev/null; then
        log_error "ffmpeg is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_warning "jq is not installed. Queue state details will be limited."
        log_info "Install with: sudo apt install jq"
    fi
    
    # Trap cleanup on exit
    trap cleanup EXIT INT TERM
    
    # Run selected scenario
    case "$SCENARIO" in
        simultaneous)
            scenario_simultaneous
            ;;
        orderly)
            scenario_orderly
            ;;
        chaos)
            scenario_chaos
            ;;
        rapid-reconnect)
            scenario_rapid_reconnect
            ;;
        queue-drain)
            scenario_queue_drain
            ;;
        all)
            scenario_all
            ;;
        *)
            log_error "Unknown scenario: $SCENARIO"
            echo ""
            print_summary
            exit 1
            ;;
    esac
    
    echo ""
    log_success "╔════════════════════════════════════════════════════════════════╗"
    log_success "║               STRESS TEST COMPLETE! ✓                          ║"
    log_success "╚════════════════════════════════════════════════════════════════╝"
    log_success "Results saved to: $RESULTS_FILE"
    echo ""
    
    # Show log location
    log_info "📁 Logs available in: $LOG_DIR/"
    log_info "📊 View results: cat $RESULTS_FILE"
    echo ""
}

# Run main if not sourced
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main
fi

