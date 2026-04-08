"""Test user creation and authentication helpers."""
import asyncio
import sys
from pathlib import Path
from typing import Any

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import httpx

from backend.tests.performance.config import TestConfig


async def create_test_user(
    client: httpx.AsyncClient,
    base_url: str,
    email: str,
    password: str,
) -> dict[str, Any] | None:
    """Create a test user via the API."""
    try:
        response = await client.post(
            f"{base_url}/auth/register",
            json={"email": email, "password": password},
            timeout=10.0,
        )
        if response.status_code == 200 or response.status_code == 201:
            return response.json()
        # User might already exist
        if response.status_code == 400:
            return {"email": email, "exists": True}
        return None
    except Exception:
        return None


async def login_user(
    client: httpx.AsyncClient,
    base_url: str,
    email: str,
    password: str,
) -> str | None:
    """Login and get JWT token."""
    try:
        response = await client.post(
            f"{base_url}/auth/login",
            data={"username": email, "password": password},
            timeout=10.0,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        return None
    except Exception:
        return None


async def create_test_users_batch(
    config: TestConfig,
) -> list[dict[str, Any]]:
    """Create a batch of test users for load testing."""
    users = []
    async with httpx.AsyncClient() as client:
        tasks = []
        for i in range(config.num_test_users):
            email = f"{config.test_user_email_prefix}_{i}@test.example.com"
            task = create_test_user(client, config.api_base_url, email, config.test_user_password)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            email = f"{config.test_user_email_prefix}_{i}@test.example.com"
            if isinstance(result, dict):
                users.append({"email": email, "password": config.test_user_password, **result})
            elif isinstance(result, Exception):
                # Log but continue
                print(f"Failed to create user {email}: {result}")

    return users


async def get_auth_tokens_batch(
    emails: list[str],
    password: str,
    base_url: str,
) -> dict[str, str]:
    """Get auth tokens for a batch of users."""
    tokens = {}
    async with httpx.AsyncClient() as client:
        tasks = []
        for email in emails:
            task = login_user(client, base_url, email, password)
            tasks.append((email, task))

        for email, task in tasks:
            token = await task
            if token:
                tokens[email] = token

    return tokens


def generate_user_credentials(user_index: int, config: TestConfig) -> tuple[str, str]:
    """Generate deterministic user credentials."""
    email = f"{config.test_user_email_prefix}_{user_index}@test.example.com"
    return email, config.test_user_password


class UserTokenPool:
    """Pool of pre-authenticated user tokens for load testing."""

    def __init__(self, config: TestConfig):
        self.config = config
        self._tokens: dict[str, str] = {}
        self._emails: list[str] = []

    async def initialize(self) -> None:
        """Initialize the token pool by creating and authenticating users."""
        print(f"Initializing token pool with {self.config.num_test_users} users...")

        # Create users
        users = await create_test_users_batch(self.config)
        print(f"Created {len(users)} users")

        # Get tokens
        emails = [u["email"] for u in users]
        self._tokens = await get_auth_tokens_batch(
            emails, self.config.test_user_password, self.config.api_base_url
        )
        self._emails = list(self._tokens.keys())
        print(f"Authenticated {len(self._tokens)} users")

    def get_random_token(self) -> str | None:
        """Get a random token from the pool."""
        import random

        if not self._tokens:
            return None
        email = random.choice(self._emails)
        return self._tokens.get(email)

    def get_token_for_user(self, user_index: int) -> str | None:
        """Get token for a specific user index."""
        email = f"{self.config.test_user_email_prefix}_{user_index}@test.example.com"
        return self._tokens.get(email)

    @property
    def size(self) -> int:
        """Return pool size."""
        return len(self._tokens)
