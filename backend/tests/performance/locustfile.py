"""Locust performance test scenarios for MuseAI.

Tests both authenticated and guest chat endpoints with SSE streaming.
"""
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import httpx
from locust import HttpUser, between, events, task

from backend.tests.performance.config import TestConfig, get_config
from backend.tests.performance.test_users import UserTokenPool


# Global config and token pool
# Get scenario from environment variable or default to 'load'
import os
_scenario = os.environ.get("PERF_TEST_SCENARIO", "load")
config = get_config(_scenario)
token_pool: UserTokenPool | None = None


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initialize test resources before test starts."""
    global token_pool

    print(f"\nStarting performance test with scenario: {config.scenario}")
    print(f"API base URL: {config.api_base_url}")

    # Initialize token pool for authenticated users
    token_pool = UserTokenPool(config)

    # Run async initialization
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(token_pool.initialize())
        print(f"Token pool initialized with {token_pool.size} users")
    finally:
        loop.close()


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Cleanup after test stops."""
    print("\nPerformance test completed")


# Test questions about museum exhibits
SAMPLE_QUESTIONS = [
    "这件青铜鼎是什么朝代的?",
    "请介绍一下青花瓷瓶的特点",
    "清明上河图描绘了什么内容?",
    "玉琮有什么文化意义?",
    "司母戊鼎有多重?",
    "古代中国馆有哪些展品?",
    "这幅画的作者是谁?",
    "这件文物出土于哪里?",
    "请讲解一下这件展品的历史背景",
    "这个展馆在三楼吗?",
]


class BaseChatUser(HttpUser):
    """Base class for chat users with common functionality."""

    abstract = True
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    def on_start(self):
        """Called when a user starts."""
        self.client.timeout = httpx.Timeout(120.0, connect=30.0)

    def parse_sse_stream(self, response, timeout: float = 60.0) -> dict[str, Any]:
        """Parse SSE stream and extract metrics."""
        chunks_received = 0
        first_chunk_time = None
        total_content = ""
        sources = []
        error = None
        trace_id = None

        start_time = time.time()

        for line in response.iter_lines():
            # Check timeout
            if time.time() - start_time > timeout:
                error = "stream_timeout"
                break

            if not line:
                continue

            # Handle bytes from Locust's streaming response
            if isinstance(line, bytes):
                line = line.decode("utf-8")

            if line.startswith("data: "):
                data_str = line[6:]  # Remove "data: " prefix

                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)

                    # Track first chunk timing
                    if first_chunk_time is None and data.get("type") in ["chunk", "rag_step"]:
                        first_chunk_time = time.time() - start_time

                    # Count chunks
                    if data.get("type") == "chunk":
                        chunks_received += 1
                        total_content += data.get("content", "")

                    # Extract sources
                    if data.get("type") == "done":
                        sources = data.get("sources", [])
                        trace_id = data.get("trace_id")

                    # Check for errors
                    if data.get("type") == "error":
                        error = data.get("code", "unknown_error")

                except json.JSONDecodeError:
                    continue

        return {
            "chunks": chunks_received,
            "first_chunk_time": first_chunk_time,
            "total_time": time.time() - start_time,
            "content_length": len(total_content),
            "sources": len(sources),
            "error": error,
            "trace_id": trace_id,
        }


class AuthenticatedChatUser(BaseChatUser):
    """Simulates an authenticated user sending chat messages."""

    weight = 3  # Relative weight for scenario mixing

    def on_start(self):
        """Get auth token on start."""
        super().on_start()
        self.token = None

        if token_pool and token_pool.size > 0:
            self.token = token_pool.get_random_token()

        if not self.token:
            # Fallback: login as a random test user
            user_index = random.randint(0, config.num_test_users - 1)
            email = f"{config.test_user_email_prefix}_{user_index}@test.example.com"

            response = self.client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": config.test_user_password},
                name="auth_login",
            )
            if response.status_code == 200:
                self.token = response.json().get("access_token")

    def get_headers(self) -> dict[str, str]:
        """Get auth headers."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @task(10)
    def send_chat_message(self):
        """Send a chat message and process SSE stream."""
        if not self.token:
            return  # Skip if not authenticated

        question = random.choice(SAMPLE_QUESTIONS)

        # Create a session first (if needed)
        session_response = self.client.post(
            "/api/v1/chat/sessions",
            json={"title": f"Performance Test Session {time.time()}"},
            headers=self.get_headers(),
            name="create_session",
        )

        if session_response.status_code != 200:
            return

        session_id = session_response.json().get("id")

        # Send chat message with streaming
        with self.client.post(
            "/api/v1/chat/ask/stream",
            json={"session_id": session_id, "message": question},
            headers=self.get_headers(),
            name="chat_stream_auth",
            catch_response=True,
            stream=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Got status {response.status_code}")
                return

            metrics = self.parse_sse_stream(response)

            if metrics.get("error"):
                response.failure(metrics["error"])
            else:
                # Report custom metrics
                response.success()

                # Log performance metrics
                if metrics.get("first_chunk_time"):
                    environment = self.environment
                    if not hasattr(environment, "custom_metrics"):
                        environment.custom_metrics = {}
                    if "first_chunk_time" not in environment.custom_metrics:
                        environment.custom_metrics["first_chunk_time"] = []
                    environment.custom_metrics["first_chunk_time"].append(metrics["first_chunk_time"])

    @task(3)
    def list_sessions(self):
        """List user's chat sessions."""
        if not self.token:
            return

        self.client.get(
            "/api/v1/chat/sessions",
            headers=self.get_headers(),
            name="list_sessions",
        )

    @task(1)
    def view_health(self):
        """Check API health."""
        self.client.get("/api/v1/health", name="health_check")


class GuestChatUser(BaseChatUser):
    """Simulates a guest user (no authentication) sending chat messages."""

    weight = 7  # Higher weight for guest users

    @task(10)
    def send_guest_message(self):
        """Send a guest chat message and process SSE stream."""
        question = random.choice(SAMPLE_QUESTIONS)

        with self.client.post(
            "/api/v1/chat/guest/message",
            json={"message": question},
            name="chat_stream_guest",
            catch_response=True,
            stream=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Got status {response.status_code}")
                return

            metrics = self.parse_sse_stream(response)

            if metrics.get("error"):
                response.failure(metrics["error"])
            else:
                response.success()

                # Capture session ID from header for follow-up
                session_id = response.headers.get("X-Session-Id")

                # Log performance metrics
                if metrics.get("first_chunk_time"):
                    environment = self.environment
                    if not hasattr(environment, "custom_metrics"):
                        environment.custom_metrics = {}
                    if "first_chunk_time" not in environment.custom_metrics:
                        environment.custom_metrics["first_chunk_time"] = []
                    environment.custom_metrics["first_chunk_time"].append(metrics["first_chunk_time"])

    @task(1)
    def view_health(self):
        """Check API health."""
        self.client.get("/api/v1/health", name="health_check_guest")


# Configure user classes based on scenario weights
def get_user_classes():
    """Get user classes with weights from config."""
    AuthenticatedChatUser.weight = config.auth_user_weight
    GuestChatUser.weight = config.guest_user_weight
    return [AuthenticatedChatUser, GuestChatUser]


# Locust will automatically discover these
user_classes = get_user_classes()
