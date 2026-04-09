#!/bin/bash
set -e

# Performance Test Runner for MuseAI
# Usage: ./run_tests.sh [scenario] [users] [run_time] [spawn_rate]
#        ./run_tests.sh --help
#
# Options:
#   --skip-api       Don't start API server (use existing)
#   --skip-infra     Don't check/start Docker infrastructure
#   --keep-running   Keep services running after test
#
# This script handles the complete test setup:
# 1. Checks/starts infrastructure (Docker)
# 2. Starts mock services (LLM + Rerank)
# 3. Starts API server with mock configuration
# 4. Prepares test data
# 5. Runs Locust performance tests
# 6. Cleans up on exit (unless --keep-running)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Parse flags
SKIP_API=false
SKIP_INFRA=false
KEEP_RUNNING=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-api)
            SKIP_API=true
            shift
            ;;
        --skip-infra)
            SKIP_INFRA=true
            shift
            ;;
        --keep-running)
            KEEP_RUNNING=true
            shift
            ;;
        --help|-h)
            echo "MuseAI Performance Test Runner"
            echo ""
            echo "Usage: ./run_tests.sh [scenario] [users] [run_time] [spawn_rate]"
            echo ""
            echo "Scenarios: smoke, load, stress, spike"
            echo ""
            echo "Options:"
            echo "  --skip-api       Don't start API server (use existing)"
            echo "  --skip-infra     Don't check/start Docker infrastructure"
            echo "  --keep-running   Keep services running after test"
            echo ""
            echo "Examples:"
            echo "  ./run_tests.sh smoke"
            echo "  ./run_tests.sh load 100 5m 20"
            echo "  ./run_tests.sh stress --skip-api"
            exit 0
            ;;
        *)
            # Positional arguments
            if [[ -z "$SCENARIO" ]]; then
                SCENARIO="$1"
            elif [[ -z "$USERS_ARG" ]]; then
                USERS_ARG="$1"
            elif [[ -z "$RUN_TIME_ARG" ]]; then
                RUN_TIME_ARG="$1"
            elif [[ -z "$SPAWN_RATE_ARG" ]]; then
                SPAWN_RATE_ARG="$1"
            fi
            shift
            ;;
    esac
done

# Mock service ports
MOCK_LLM_PORT=8099
MOCK_RERANK_PORT=8098

# API server port
API_PORT=8000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track PIDs for cleanup
MOCK_LLM_PID=""
MOCK_RERANK_PID=""
API_PID=""

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         MuseAI Performance Test Runner                    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
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

echo -e "${BLUE}Test Configuration:${NC}"
echo "  Scenario:   $SCENARIO"
echo "  Users:      $USERS"
echo "  Run Time:   $RUN_TIME"
echo "  Spawn Rate: $SPAWN_RATE/sec"
echo ""

# ============================================================================
# Cleanup function
# ============================================================================
cleanup() {
    if [ "$KEEP_RUNNING" = true ]; then
        echo ""
        echo -e "${GREEN}Keeping services running (--keep-running)${NC}"
        echo "  Mock LLM:     http://localhost:${MOCK_LLM_PORT}"
        echo "  Mock Rerank:  http://localhost:${MOCK_RERANK_PORT}"
        echo "  API Server:   http://localhost:${API_PORT}"
        return
    fi

    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"

    # Kill mock servers
    if [ -n "$MOCK_LLM_PID" ] && kill -0 "$MOCK_LLM_PID" 2>/dev/null; then
        kill "$MOCK_LLM_PID" 2>/dev/null
        wait "$MOCK_LLM_PID" 2>/dev/null
        echo "  ✓ Stopped mock LLM server"
    fi

    if [ -n "$MOCK_RERANK_PID" ] && kill -0 "$MOCK_RERANK_PID" 2>/dev/null; then
        kill "$MOCK_RERANK_PID" 2>/dev/null
        wait "$MOCK_RERANK_PID" 2>/dev/null
        echo "  ✓ Stopped mock rerank server"
    fi

    # Kill API server if we started it
    if [ -n "$API_PID" ] && kill -0 "$API_PID" 2>/dev/null; then
        kill "$API_PID" 2>/dev/null
        wait "$API_PID" 2>/dev/null
        echo "  ✓ Stopped API server"
    fi

    echo -e "${GREEN}Cleanup complete${NC}"
}
trap cleanup EXIT

# ============================================================================
# Helper functions
# ============================================================================
wait_for_server() {
    local url="$1"
    local max_retries="${2:-10}"
    local retry_count=0

    while [ $retry_count -lt $max_retries ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            return 0
        fi
        retry_count=$((retry_count + 1))
        sleep 1
    done
    return 1
}

check_port_available() {
    local port="$1"
    if lsof -i :"$port" > /dev/null 2>&1; then
        return 1
    fi
    return 0
}

# ============================================================================
# Step 1: Check infrastructure (Docker)
# ============================================================================
echo -e "${YELLOW}Step 1: Checking infrastructure...${NC}"
cd "$PROJECT_ROOT"

if [ "$SKIP_INFRA" = true ]; then
    echo -e "${YELLOW}  Skipping infrastructure check (--skip-infra)${NC}"
else
    # Check if docker-compose is available and services are running
    if command -v docker &> /dev/null && [ -f "docker-compose.yml" ]; then
        # Check PostgreSQL
        if ! docker compose ps postgres 2>/dev/null | grep -q "running"; then
            echo -e "${BLUE}  Starting Docker services...${NC}"
            docker compose up -d
            sleep 5
        fi
        echo -e "${GREEN}  ✓ Docker services running${NC}"
    else
        echo -e "${YELLOW}  ! Docker not available, assuming services are external${NC}"
    fi
fi

# ============================================================================
# Step 2: Check ports and kill conflicting processes
# ============================================================================
echo -e "${YELLOW}Step 2: Checking ports...${NC}"

# Check mock service ports
for port in $MOCK_LLM_PORT $MOCK_RERANK_PORT; do
    if ! check_port_available "$port"; then
        echo -e "${YELLOW}  Port $port is in use, attempting to free it...${NC}"
        fuser -k "$port/tcp" 2>/dev/null || true
        sleep 1
    fi
done

echo -e "${GREEN}  ✓ Ports available${NC}"

# ============================================================================
# Step 3: Start mock services
# ============================================================================
echo -e "${YELLOW}Step 3: Starting mock services...${NC}"

# Start mock LLM server
MOCK_LLM_LOG="/tmp/mock_llm_server.log"
uv run python backend/tests/performance/mock_llm_server.py > "$MOCK_LLM_LOG" 2>&1 &
MOCK_LLM_PID=$!
echo "  Mock LLM PID: $MOCK_LLM_PID"

if ! wait_for_server "http://localhost:${MOCK_LLM_PORT}/health" 10; then
    echo -e "${RED}  ✗ Mock LLM server failed to start${NC}"
    cat "$MOCK_LLM_LOG"
    exit 1
fi
echo -e "${GREEN}  ✓ Mock LLM server running on port $MOCK_LLM_PORT${NC}"

# Start mock Rerank server
MOCK_RERANK_LOG="/tmp/mock_rerank_server.log"
uv run python backend/tests/performance/mock_rerank_server.py > "$MOCK_RERANK_LOG" 2>&1 &
MOCK_RERANK_PID=$!
echo "  Mock Rerank PID: $MOCK_RERANK_PID"

if ! wait_for_server "http://localhost:${MOCK_RERANK_PORT}/health" 10; then
    echo -e "${RED}  ✗ Mock Rerank server failed to start${NC}"
    cat "$MOCK_RERANK_LOG"
    exit 1
fi
echo -e "${GREEN}  ✓ Mock Rerank server running on port $MOCK_RERANK_PORT${NC}"

# ============================================================================
# Step 4: Check/Start API server
# ============================================================================
echo -e "${YELLOW}Step 4: Checking API server...${NC}"

# Check if API is already running
if curl -s "http://localhost:${API_PORT}/api/v1/health" > /dev/null 2>&1; then
    if [ "$SKIP_API" = true ]; then
        echo -e "${GREEN}  ✓ API server already running on port $API_PORT (--skip-api)${NC}"
        echo -e "${YELLOW}  ! WARNING: Ensure the API server is configured to use mock services:${NC}"
        echo "      LLM_BASE_URL=http://localhost:${MOCK_LLM_PORT}/v1"
        echo "      RERANK_BASE_URL=http://localhost:${MOCK_RERANK_PORT}"
    else
        # API is running but we need it with mock configuration
        echo -e "${YELLOW}  API server already running on port $API_PORT${NC}"
        echo -e "${BLUE}  Stopping existing API server to restart with mock services...${NC}"

        # Find and kill the existing uvicorn process
        EXISTING_PID=$(lsof -t -i :${API_PORT} 2>/dev/null | head -1)
        if [ -n "$EXISTING_PID" ]; then
            # Kill the process tree (parent uvicorn + child)
            pkill -P "$EXISTING_PID" 2>/dev/null || true
            kill "$EXISTING_PID" 2>/dev/null || true
            sleep 2

            # Force kill if still running
            if lsof -i :${API_PORT} > /dev/null 2>&1; then
                echo -e "${YELLOW}    Force killing remaining processes...${NC}"
                fuser -k ${API_PORT}/tcp 2>/dev/null || true
                sleep 1
            fi
            echo -e "${GREEN}  ✓ Stopped existing API server${NC}"
        fi
    fi
fi

# Start API server if not running or if we stopped it above
if [ "$SKIP_API" = true ] && curl -s "http://localhost:${API_PORT}/api/v1/health" > /dev/null 2>&1; then
    : # Already running and --skip-api, do nothing
elif [ "$SKIP_API" = true ]; then
    echo -e "${RED}  ✗ API server not running and --skip-api specified${NC}"
    echo "     Please start the API server manually or remove --skip-api"
    exit 1
else
    echo -e "${BLUE}  Starting API server with mock services...${NC}"

    # Start API server with mock configuration
    API_LOG="/tmp/api_server.log"
    APP_ENV=development \
    LLM_BASE_URL="http://localhost:${MOCK_LLM_PORT}/v1" \
    LLM_API_KEY="mock-key" \
    LLM_MODEL="mock-model" \
    RERANK_BASE_URL="http://localhost:${MOCK_RERANK_PORT}" \
    RERANK_API_KEY="mock-key" \
    RERANK_MODEL="mock-rerank-model" \
    uv run uvicorn backend.app.main:app --port "$API_PORT" > "$API_LOG" 2>&1 &
    API_PID=$!
    echo "  API PID: $API_PID"

    if ! wait_for_server "http://localhost:${API_PORT}/api/v1/health" 30; then
        echo -e "${RED}  ✗ API server failed to start${NC}"
        cat "$API_LOG"
        exit 1
    fi
    echo -e "${GREEN}  ✓ API server running on port $API_PORT with mock services${NC}"
fi

# ============================================================================
# Step 5: Prepare test data
# ============================================================================
echo -e "${YELLOW}Step 5: Preparing test data...${NC}"
uv run python backend/tests/performance/prepare_test_data.py --scenario "$SCENARIO"
echo -e "${GREEN}  ✓ Test data prepared${NC}"

# ============================================================================
# Step 6: Run Locust
# ============================================================================
echo ""
echo -e "${YELLOW}Step 6: Running Locust performance test...${NC}"
echo ""

REPORT_DIR="${PROJECT_ROOT}/performance_reports"
mkdir -p "$REPORT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="${REPORT_DIR}/report_${SCENARIO}_${TIMESTAMP}.html"

cd "${SCRIPT_DIR}"

# Set environment for mock services (in case API was already running)
export LLM_BASE_URL="http://localhost:${MOCK_LLM_PORT}/v1"
export LLM_API_KEY="mock-key"
export LLM_MODEL="mock-model"
export RERANK_BASE_URL="http://localhost:${MOCK_RERANK_PORT}"
export RERANK_API_KEY="mock-key"
export RERANK_MODEL="mock-rerank-model"

# Pass scenario to locustfile via environment variable
export PERF_TEST_SCENARIO="$SCENARIO"

uv run locust -f locustfile.py \
    --host "http://localhost:${API_PORT}" \
    --users "$USERS" \
    --run-time "$RUN_TIME" \
    --spawn-rate "$SPAWN_RATE" \
    --html "$REPORT_FILE" \
    --headless \
    --only-summary

# ============================================================================
# Step 7: Analyze results
# ============================================================================
echo ""
echo -e "${GREEN}Performance test completed!${NC}"
echo "Report saved to: $REPORT_FILE"

echo ""
echo -e "${YELLOW}Step 7: Analyzing results...${NC}"
cd "$PROJECT_ROOT"

if [ -f "backend/tests/performance/analyze_results.py" ]; then
    uv run python backend/tests/performance/analyze_results.py "$REPORT_FILE"
else
    echo -e "${YELLOW}  analyze_results.py not found, skipping analysis${NC}"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Test Complete                          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
