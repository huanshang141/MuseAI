"""Tests for client IP extraction with trusted proxy support."""

import pytest
from unittest.mock import MagicMock

from app.api.client_ip import extract_client_ip


def test_ignores_xff_when_request_not_from_trusted_proxy():
    """X-Forwarded-For should be ignored when the peer is not a trusted proxy."""
    # Mock request with X-Forwarded-For header from untrusted peer
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = "8.8.8.8"  # Untrusted peer IP
    request.headers = {"X-Forwarded-For": "1.2.3.4"}

    trusted_proxies = {"10.0.0.1"}  # Does not include 8.8.8.8

    ip = extract_client_ip(request, trusted_proxies)
    assert ip == "8.8.8.8"  # Should use peer IP, not X-Forwarded-For


def test_uses_xff_when_request_from_trusted_proxy():
    """X-Forwarded-For should be used when the peer is a trusted proxy."""
    # Mock request with X-Forwarded-For header from trusted proxy
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = "10.0.0.1"  # Trusted proxy IP
    request.headers = {"X-Forwarded-For": "1.2.3.4"}

    trusted_proxies = {"10.0.0.1"}  # Includes the peer

    ip = extract_client_ip(request, trusted_proxies)
    assert ip == "1.2.3.4"  # Should use X-Forwarded-For


def test_uses_first_ip_from_xff_chain():
    """Should use the first IP from a multi-hop X-Forwarded-For chain."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = "10.0.0.1"
    request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8, 9.10.11.12"}

    trusted_proxies = {"10.0.0.1"}

    ip = extract_client_ip(request, trusted_proxies)
    assert ip == "1.2.3.4"  # First IP in the chain


def test_strips_whitespace_from_xff():
    """Should strip whitespace from X-Forwarded-For values."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = "10.0.0.1"
    request.headers = {"X-Forwarded-For": "  1.2.3.4 , 5.6.7.8  "}

    trusted_proxies = {"10.0.0.1"}

    ip = extract_client_ip(request, trusted_proxies)
    assert ip == "1.2.3.4"  # Whitespace stripped


def test_returns_peer_ip_when_no_xff():
    """Should return peer IP when X-Forwarded-For is not present."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = "8.8.8.8"
    request.headers = {}

    trusted_proxies = {"10.0.0.1"}

    ip = extract_client_ip(request, trusted_proxies)
    assert ip == "8.8.8.8"


def test_returns_unknown_when_no_client():
    """Should return 'unknown' when request.client is None."""
    request = MagicMock()
    request.client = None
    request.headers = {}

    trusted_proxies = {"10.0.0.1"}

    ip = extract_client_ip(request, trusted_proxies)
    assert ip == "unknown"


def test_ignores_xff_when_no_client_even_if_trusted_proxy():
    """Should ignore X-Forwarded-For when client is None, even from trusted proxy."""
    request = MagicMock()
    request.client = None
    request.headers = {"X-Forwarded-For": "1.2.3.4"}

    trusted_proxies = {"10.0.0.1"}

    ip = extract_client_ip(request, trusted_proxies)
    assert ip == "unknown"


def test_empty_trusted_proxies_ignores_xff():
    """Empty trusted proxies set should always ignore X-Forwarded-For."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = "8.8.8.8"
    request.headers = {"X-Forwarded-For": "1.2.3.4"}

    trusted_proxies = set()  # Empty set

    ip = extract_client_ip(request, trusted_proxies)
    assert ip == "8.8.8.8"


def test_multiple_trusted_proxies():
    """Should trust XFF from any configured trusted proxy."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = "10.0.0.5"
    request.headers = {"X-Forwarded-For": "1.2.3.4"}

    trusted_proxies = {"10.0.0.1", "10.0.0.2", "10.0.0.5"}

    ip = extract_client_ip(request, trusted_proxies)
    assert ip == "1.2.3.4"
