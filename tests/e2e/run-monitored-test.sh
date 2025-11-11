#!/bin/bash
# run-monitored-test.sh
# Helper script to run e2e tests while monitoring OBS source health
# Usage: ./run-monitored-test.sh [test-scenario] [poll-interval]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
TEST_SCENARIO=${1:-"orderly"}
POLL_INTERVAL=${2:-"0.2"}
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_DIR="logs2"
MONITOR_OUTPUT="$LOG_DIR/obs-monitor-$TIMESTAMP.csv"
MONITOR_PID=""

# Ensure logs2 directory exists
mkdir -p "$LOG_DIR"

# Function to cleanup on exit
cleanup() {
    if [ ! -z "$MONITOR_PID" ] && kill -0 $MONITOR_PID 2>/dev/null; then
        echo -e "\n${YELLOW}Stopping OBS monitor...${NC}"
        kill -INT $MONITOR_PID
        wait $MONITOR_PID 2>/dev/null || true
        echo -e "${GREEN}✓ Monitor stopped${NC}"
    fi
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Display banner
echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}OBS Monitored E2E Test${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""
echo -e "Test Scenario:  ${GREEN}$TEST_SCENARIO${NC}"
echo -e "Poll Interval:  ${GREEN}${POLL_INTERVAL}s${NC}"
echo -e "Monitor Output: ${GREEN}$MONITOR_OUTPUT${NC}"
echo ""

# Check if OBS environment variables are set
if [ -z "$OBS_PASSWORD" ]; then
    echo -e "${YELLOW}⚠️  OBS_PASSWORD not set in environment${NC}"
    
    # Try to load from .env.prod
    if [ -f ".env.prod" ]; then
        echo -e "${BLUE}Loading OBS credentials from .env.prod...${NC}"
        export $(grep -E "^OBS_" .env.prod | xargs)
        echo -e "${GREEN}✓ Credentials loaded${NC}"
    else
        echo -e "${RED}✗ .env.prod not found${NC}"
        echo -e "${RED}Please set OBS_HOST, OBS_PORT, and OBS_PASSWORD environment variables${NC}"
        exit 1
    fi
fi

echo ""

# Start the OBS monitor in the background
echo -e "${BLUE}Starting OBS monitor...${NC}"
python3 tests/e2e/obs-stream-switch-monitor.py \
    --output "$MONITOR_OUTPUT" \
    --poll-interval "$POLL_INTERVAL" &

MONITOR_PID=$!
echo -e "${GREEN}✓ Monitor started (PID: $MONITOR_PID)${NC}"
echo ""

# Give monitor time to initialize
sleep 2

# Check if monitor is still running
if ! kill -0 $MONITOR_PID 2>/dev/null; then
    echo -e "${RED}✗ Monitor failed to start. Check OBS connection.${NC}"
    exit 1
fi

echo -e "${BLUE}Starting e2e test: $TEST_SCENARIO${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""

# Run the e2e test
if [ -f "tests/e2e/motherstream-stress-test.sh" ]; then
    ./tests/e2e/motherstream-stress-test.sh "$TEST_SCENARIO"
    TEST_EXIT_CODE=$?
else
    echo -e "${RED}✗ Test script not found: tests/e2e/motherstream-stress-test.sh${NC}"
    TEST_EXIT_CODE=1
fi

echo ""
echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}Test completed with exit code: $TEST_EXIT_CODE${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""

# Stop the monitor (cleanup function will handle this)
echo -e "${YELLOW}Stopping monitor and generating report...${NC}"

# Cleanup will be called automatically

# Wait a moment for report generation
sleep 2

# Show report location
REPORT_FILE="${MONITOR_OUTPUT%.csv}-report.txt"
echo ""
echo -e "${GREEN}=================================${NC}"
echo -e "${GREEN}Monitoring Complete${NC}"
echo -e "${GREEN}=================================${NC}"
echo ""
echo -e "CSV Data:  ${BLUE}$MONITOR_OUTPUT${NC}"
if [ -f "$REPORT_FILE" ]; then
    echo -e "Report:    ${BLUE}$REPORT_FILE${NC}"
    echo ""
    echo -e "${YELLOW}Report Summary:${NC}"
    echo ""
    # Show relevant parts of the report
    tail -n 20 "$REPORT_FILE"
else
    echo -e "${YELLOW}⚠️  Report not generated (no state changes detected?)${NC}"
fi

echo ""
echo -e "${GREEN}=================================${NC}"
echo ""

exit $TEST_EXIT_CODE

