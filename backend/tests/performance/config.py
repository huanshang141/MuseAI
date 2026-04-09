"""Performance test configuration.

All configurable parameters for load testing.
"""
from dataclasses import dataclass
from typing import Literal


@dataclass
class TestConfig:
    """Test configuration settings."""

    # Server endpoints
    api_base_url: str = "http://localhost:8000/api/v1"
    mock_llm_host: str = "0.0.0.0"
    mock_llm_port: int = 8099

    # Mock LLM settings
    mock_llm_min_delay_ms: int = 500  # Minimum streaming delay
    mock_llm_max_delay_ms: int = 2000  # Maximum streaming delay
    mock_llm_chunk_size: int = 20  # Characters per chunk
    mock_llm_response_length: int = 500  # Total response length in chars

    # Mock Rerank settings
    mock_rerank_host: str = "0.0.0.0"
    mock_rerank_port: int = 8098
    mock_rerank_min_delay_ms: int = 50  # Base rerank delay
    mock_rerank_max_delay_ms: int = 200  # Additional random delay

    # Locust settings
    spawn_rate: int = 10  # Users per second
    run_time: str = "5m"  # Default test duration

    # Test scenarios
    auth_user_weight: int = 3  # Weight for authenticated user scenario
    guest_user_weight: int = 7  # Weight for guest user scenario

    # Test data
    num_test_users: int = 100  # Number of test users to create
    test_user_password: str = "TestPass123!"
    test_user_email_prefix: str = "perftest"

    # Elasticsearch test data
    num_test_documents: int = 50  # Number of test documents in ES

    # Resource monitoring
    enable_monitoring: bool = True
    metrics_interval_seconds: int = 5

    # Scenarios
    scenario: Literal["smoke", "load", "stress", "spike"] = "load"


# Preset scenarios
SCENARIOS = {
    "smoke": TestConfig(
        scenario="smoke",
        spawn_rate=5,
        run_time="2m",
        auth_user_weight=1,
        guest_user_weight=1,
        num_test_users=10,
    ),
    "load": TestConfig(
        scenario="load",
        spawn_rate=10,
        run_time="5m",
        auth_user_weight=3,
        guest_user_weight=7,
        num_test_users=100,
    ),
    "stress": TestConfig(
        scenario="stress",
        spawn_rate=20,
        run_time="10m",
        auth_user_weight=5,
        guest_user_weight=5,
        num_test_users=500,
    ),
    "spike": TestConfig(
        scenario="spike",
        spawn_rate=50,
        run_time="3m",
        auth_user_weight=3,
        guest_user_weight=7,
        num_test_users=200,
    ),
}


def get_config(scenario: str = "load") -> TestConfig:
    """Get configuration for a specific test scenario."""
    return SCENARIOS.get(scenario, SCENARIOS["load"])
