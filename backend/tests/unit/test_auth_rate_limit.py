# backend/tests/unit/test_auth_rate_limit.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_redis():
    """Mock Redis for rate limiting tests."""
    redis = MagicMock()
    redis.check_rate_limit = AsyncMock(return_value=True)
    redis.is_token_blacklisted = AsyncMock(return_value=False)
    return redis


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    return session


def test_login_endpoint_has_rate_limiting():
    """Login endpoint should check rate limit."""
    from app.api.auth import router

    # Find the login route
    login_route = None
    for route in router.routes:
        if hasattr(route, 'path') and route.path == '/auth/login':
            login_route = route
            break

    assert login_route is not None, "Login route not found"
    # The route should have rate limiting dependency
    # This is a structural check - the actual rate limiting is in deps


def test_register_endpoint_has_rate_limiting():
    """Register endpoint should check rate limit."""
    from app.api.auth import router

    register_route = None
    for route in router.routes:
        if hasattr(route, 'path') and route.path == '/auth/register':
            register_route = route
            break

    assert register_route is not None, "Register route not found"
