#!/bin/bash
set -e

# Performance Test Runner for MuseAI
# Usage: ./run_tests.sh [scenario] [options]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Default values
SCENARIO="${1:-load}"
USERS="${2:-}"
RUN_TIME="${3:-}"
SPAWN_RATE="${4:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}MuseAI Performance Test Runner${NC}"
echo "======================================"
echo ""

# Parse scenario-specific defaults
case $SCENARIO in
    smoke)
        DEFAULT_USERS=10
        DEFAULT_RUN_TIME="2m"
        DEFAULT_SPAWN_RATE=5
        ;;
    load)
        DEFAULT_USERS=50
        DEFAULT_RUN_TIME="5m"
        DEFAULT_SPAWN_RATE=10
        ;;
    stress)
        DEFAULT_USERS=200
        DEFAULT_RUN_TIME="10m"
        DEFAULT_SPAWN_RATE=20
        ;;
    spike)
        DEFAULT_USERS=100
        DEFAULT_RUN_TIME="3m"
        DEFAULT_SPAWN_RATE=50
        ;;
    *)
        echo -e "${RED}Unknown scenario: $SCENARIO${NC}"
        echo "Available scenarios: smoke, load, stress, spike"
        exit 1
        ;;
esac

# Apply overrides or use defaults
USERS="${USERS:-$DEFAULT_USERS}"
RUN_TIME="${RUN_TIME:-$DEFAULT_RUN_TIME}"
SPAWN_RATE="${SPAWN_RATE:-$DEFAULT_SPAWN_RATE}"

echo "Scenario: $SCENARIO"
echo "Users: $USERS"
echo "Run Time: $RUN_TIME"
echo "Spawn Rate: $SPAWN_RATE/sec"
echo ""

# Step 1: Check if services are running
echo -e "${YELLOW}Step 1: Checking services...${NC}"
if ! curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo -e "${RED}Error: API server is not running at http://localhost:8000${NC}"
    echo "Please start the server with: uv run uvicorn backend.app.main:app --reload"
    exit 1
fi
echo -e "${GREEN}✓ API server is running${NC}"

# Step 2: Prepare test data
echo -e "${YELLOW}Step 2: Preparing test data...${NC}"
cd "$PROJECT_ROOT"
uv run python -m backend.tests.performance.prepare_test_data --scenario "$SCENARIO"
echo -e "${GREEN}✓ Test data prepared${NC}"

# Step 3: Start mock LLM server (in background)
echo -e "${YELLOW}Step 3: Starting mock LLM server...${NC}"
MOCK_LLM_LOG="/tmp/mock_llm_server.log"
uv run python -m backend.tests.performance.mock_llm_server > "$MOCK_LLM_LOG" 2>&1 &
MOCK_PID=$!
echo "Mock LLM server PID: $MOCK_PID"

# Wait for mock server to start
sleep 3
if ! curl -s http://localhost:8099/health > /dev/null 2>&1; then
    echo -e "${RED}Error: Mock LLM server failed to start${NC}"
    cat "$MOCK_LLM_LOG"
    exit 1
fi
echo -e "${GREEN}✓ Mock LLM server running on port 8099${NC}"

# Trap to cleanup on exit
cleanup() {
    echo -e "${YELLOW}Cleaning up...${NC}"
    if kill -0 "$MOCK_PID" 2>/dev/null; then
        kill "$MOCK_PID"
        wait "$MOCK_PID" 2>/dev/null
        echo "Stopped mock LLM server"
    fi
}
trap cleanup EXIT

# Step 4: Configure environment for mock LLM
export LLM_BASE_URL="http://localhost:8099/v1"
export LLM_API_KEY="mock-key"
export LLM_MODEL="mock-model"

# Step 5: Run Locust
echo -e "${YELLOW}Step 5: Running Locust performance test...${NC}"
echo ""

REPORT_DIR="${PROJECT_ROOT}/performance_reports"
mkdir -p "$REPORT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="${REPORT_DIR}/report_${SCENARIO}_${TIMESTAMP}.html"

cd "${SCRIPT_DIR}"
uv run locust -f locustfile.py \
    --host http://localhost:8000 \
    --users "$USERS" \
    --run-time "$RUN_TIME" \
    --spawn-rate "$SPAWN_RATE" \
    --html "$REPORT_FILE" \
    --headless \
    --only-summary

echo ""
echo -e "${GREEN}Performance test completed!${NC}"
echo "Report saved to: $REPORT_FILE"

# Step 6: Analyze results
echo ""
echo -e "${YELLOW}Step 6: Analyzing results...${NC}"
uv run python -m backend.tests.performance.analyze_results "$REPORT_FILE"
