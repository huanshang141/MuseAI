"""Centralized client IP extraction with trusted proxy support.

This module provides a secure way to extract client IP addresses from requests,
only trusting X-Forwarded-For headers when the request comes from a configured
trusted proxy.

Security Considerations:
- X-Forwarded-For headers can be spoofed by malicious clients
- Only trust this header when the request originates from known proxy servers
- Configure TRUSTED_PROXIES in settings with your load balancer/proxy IPs
"""

from fastapi import Request


def extract_client_ip(request: Request, trusted_proxies: set[str]) -> str:
    """Extract client IP address from request, respecting trusted proxies.

    Args:
        request: The FastAPI/Starlette request object
        trusted_proxies: Set of IP addresses that are trusted to send valid
                        X-Forwarded-For headers (e.g., load balancers, reverse proxies)

    Returns:
        The client IP address. If the request comes from a trusted proxy and
        includes an X-Forwarded-For header, returns the first IP in the chain.
        Otherwise, returns the direct peer IP address.

    Examples:
        >>> # Request from untrusted peer with spoofed XFF
        >>> extract_client_ip(request, trusted_proxies={"10.0.0.1"})
        "8.8.8.8"  # Returns peer IP, ignores XFF

        >>> # Request from trusted proxy with valid XFF
        >>> extract_client_ip(request, trusted_proxies={"10.0.0.1"})
        "1.2.3.4"  # Returns XFF value
    """
    # Get the direct peer IP address
    peer_ip = request.client.host if request.client else "unknown"

    # Only trust X-Forwarded-For if the peer is a trusted proxy
    if peer_ip in trusted_proxies:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            # X-Forwarded-For format: client, proxy1, proxy2, ...
            # The leftmost value is the original client
            return xff.split(",")[0].strip()

    return peer_ip
