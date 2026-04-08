# MuseAI Performance Testing Suite

Comprehensive load testing suite for the MuseAI Museum AI Guide System using Locust.

## Overview

This suite tests the performance of chat endpoints under various load conditions:

- **Authenticated Chat** (`/api/v1/chat/ask/stream`) - Full RAG pipeline with user authentication
- **Guest Chat** (`/api/v1/chat/guest/message`) - Guest mode without authentication

## Prerequisites

1. **Running Services**:
   ```bash
   # Start all infrastructure services
   docker-compose up -d

   # Start the API server with test environment settings
   # IMPORTANT: APP_ENV must NOT be 'production' to bypass rate limiting for load testing
   APP_ENV=development \
   LLM_BASE_URL=http://localhost:8099/v1 \
   LLM_API_KEY=mock-key \
   LLM_MODEL=mock-model \
   uv run uvicorn backend.app.main:app --reload
   ```

   **Environment Variables for Performance Testing:**

   | Variable | Value | Purpose |
   |----------|-------|---------|
   | `APP_ENV` | `development` (or any value except `production`) | Bypasses rate limiting to allow high-concurrency user creation and login |
   | `LLM_BASE_URL` | `http://localhost:8099/v1` | Points to mock LLM server instead of real LLM |
   | `LLM_API_KEY` | `mock-key` | Mock API key for mock LLM server |
   | `LLM_MODEL` | `mock-model` | Mock model name |

   **Why `APP_ENV` matters:**
   - In `production` mode: Rate limiting is enforced (100 auth requests/min per IP)
   - In non-production mode (`development`, `test`, `local`, etc.): Rate limiting is bypassed entirely
   - This allows load tests to simulate realistic high-concurrency scenarios without being blocked

2. **Install Test Dependencies**:
   ```bash
   # Install dev dependencies (includes locust)
   uv sync --extra dev
   
   # Or install only performance testing dependencies
   uv sync --extra performance
   ```

## Quick Start

### Run a smoke test (10 users, 2 minutes)
```bash
./backend/tests/performance/run_tests.sh smoke
```

### Run a load test (50 users, 5 minutes)
```bash
./backend/tests/performance/run_tests.sh load
```

### Run a stress test (200 users, 10 minutes)
```bash
./backend/tests/performance/run_tests.sh stress
```

### Run a spike test (100 users, 3 minutes, fast spawn)
```bash
./backend/tests/performance/run_tests.sh spike
```

## Test Scenarios

| Scenario | Users | Duration | Spawn Rate | Purpose |
|----------|-------|----------|------------|---------|
| smoke    | 10    | 2m       | 5/s        | Basic validation |
| load     | 50    | 5m       | 10/s       | Normal load |
| stress   | 200   | 10m      | 20/s       | High load |
| spike    | 100   | 3m       | 50/s       | Sudden load |

## Custom Test Configuration

Override default parameters:

```bash
# Run with 100 users for 10 minutes, spawning 20 users/sec
./run_tests.sh load 100 10m 20
```

## Manual Test Execution

### 1. Start Mock LLM Server

```bash
uv run python -m backend.tests.performance.mock_llm_server
```

This starts a mock OpenAI-compatible server on `http://localhost:8099`.

### 2. Prepare Test Data

```bash
uv run python -m backend.tests.performance.prepare_test_data --scenario load
```

This creates:
- Test users in the database
- Test documents in Elasticsearch

### 3. Run Locust

```bash
cd backend/tests/performance

# Web UI mode
uv run locust -f locustfile.py --host http://localhost:8000

# Headless mode
uv run locust -f locustfile.py \
    --host http://localhost:8000 \
    --users 50 \
    --run-time 5m \
    --spawn-rate 10 \
    --headless
```

## Mock LLM Server

The mock server simulates an OpenAI-compatible API with configurable delays:

- **Streaming delay**: 500ms - 2000ms per chunk
- **Chunk size**: 20 characters
- **Response length**: 500 characters

Configuration in `config.py`:

```python
mock_llm_min_delay_ms: int = 500
mock_llm_max_delay_ms: int = 2000
mock_llm_chunk_size: int = 20
mock_llm_response_length: int = 500
```

## Metrics Collected

### Response Time Metrics
- **First Chunk Time** - Time to first SSE event (TTFB for streaming)
- **Total Response Time** - Complete request duration
- **P50/P95/P99** - Percentile latencies

### Throughput Metrics
- **Requests per Second (RPS)** - Overall request rate
- **Chunks per Response** - Streaming chunk count

### Resource Metrics
- **CPU Usage** - Process CPU utilization
- **Memory Usage** - Process memory consumption
- **Connection Pool** - Database/Redis connection stats

### Error Metrics
- **Error Rate** - Percentage of failed requests
- **Error Types** - Categorized failure reasons

## Test User Management

Test users are automatically created with the following pattern:

```
Email: perftest_0@test.example.com, perftest_1@test.example.com, ...
Password: TestPass123!
```

Users are created:
1. In PostgreSQL database (via `prepare_test_data.py`)
2. Authenticated tokens are pooled for load testing

## Results and Reports

### HTML Report
Generated at `performance_reports/report_<scenario>_<timestamp>.html`

Contains:
- Request statistics
- Response time distribution
- Failure details
- Charts and graphs

### Summary Report
Generated at `performance_reports/report_<scenario>_<timestamp>_summary.txt`

Text summary of key metrics.

## Troubleshooting

### "API server is not running"
```bash
# Check if server is running
curl http://localhost:8000/api/v1/health

# Start server with correct environment variables
APP_ENV=development \
LLM_BASE_URL=http://localhost:8099/v1 \
LLM_API_KEY=mock-key \
LLM_MODEL=mock-model \
uv run uvicorn backend.app.main:app --reload
```

### "429 Too Many Requests" during user creation
This means the API server is running in production mode. Restart with `APP_ENV=development`:
```bash
# Stop current server, then restart with:
APP_ENV=development uv run uvicorn backend.app.main:app --reload
```

### "Mock LLM server failed to start"
```bash
# Check if port 8099 is available
lsof -i :8099

# Check logs
cat /tmp/mock_llm_server.log
```

### "Redis connection refused"
```bash
# Check Redis is running
docker-compose ps redis

# Restart Redis
docker-compose restart redis
```

### "Database connection error"
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Restart PostgreSQL
docker-compose restart postgres
```

## Extending the Tests

### Add New Endpoints

Edit `locustfile.py` and add new tasks:

```python
@task(5)
def new_endpoint_test(self):
    """Test a new endpoint."""
    self.client.get("/api/v1/new-endpoint", name="new_endpoint")
```

### Customize Test Data

Edit `prepare_test_data.py` to add more sample documents:

```python
SAMPLE_DOCUMENTS = [
    {"title": "...", "content": "...", ...},
    # Add more documents
]
```

### Add Custom Metrics

Edit `locustfile.py` to track custom metrics:

```python
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    # Custom metric handling
    pass
```

## Best Practices

1. **Start with smoke tests** - Validate the test setup before running larger tests
2. **Monitor resources** - Watch CPU/memory during tests
3. **Use realistic delays** - Mock server delays should match real LLM latency
4. **Test incrementally** - Gradually increase load to find breaking points
5. **Save results** - Keep test reports for comparison over time

## CI/CD Integration

To run in CI/CD pipeline:

```yaml
# .github/workflows/performance-test.yml
- name: Run performance tests
  run: |
    docker-compose up -d
    sleep 30
    # Start API server with test environment (bypasses rate limiting)
    APP_ENV=development \
    LLM_BASE_URL=http://localhost:8099/v1 \
    LLM_API_KEY=mock-key \
    LLM_MODEL=mock-model \
    uv run uvicorn backend.app.main:app &
    sleep 10
    cd backend/tests/performance
    ./run_tests.sh smoke 10 2m 5
```
