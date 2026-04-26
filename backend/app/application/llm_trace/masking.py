from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "secret",
        "authorization",
        "password",
        "access_token",
        "refresh_token",
        "id_token",
        "auth",
        "private_key",
        "client_secret",
    }
)

_SENSITIVE_KEY_SUBSTRINGS = frozenset(
    {
        "token",
        "key",
    }
)

_SAFE_KEY_SUFFIXES = frozenset(
    {
        "tokens",
    }
)

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_PATTERN = re.compile(r"\b1[3-9]\d{9}\b")
_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE)
_JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_\-]*\.eyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*")
_URL_SENSITIVE_QUERY_KEYS = frozenset(
    {"api_key", "token", "secret", "password", "auth", "key"}
)

_SAFE_PLACEHOLDER = "[REDACTED]"
_MASKING_FAILED = "[MASKING_FAILED]"


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    if key_lower in _SENSITIVE_KEYS:
        return True
    for suffix in _SAFE_KEY_SUFFIXES:
        if key_lower.endswith(suffix):
            return False
    return any(sk in key_lower for sk in _SENSITIVE_KEY_SUBSTRINGS)


def mask_json(data: Any) -> Any:
    try:
        if not isinstance(data, (dict, list, str, int, float, bool, type(None))):
            return _MASKING_FAILED
        return _mask_json_value(data)
    except Exception:
        logger.warning("mask_json failed, returning safe placeholder", exc_info=True)
        return _MASKING_FAILED


def _mask_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _SAFE_PLACEHOLDER if _is_sensitive_key(k) else _mask_json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_json_value(item) for item in value]
    if isinstance(value, str):
        return mask_text(value)
    return value


def mask_text(text: str) -> str:
    try:
        result = _EMAIL_PATTERN.sub(_SAFE_PLACEHOLDER, text)
        result = _PHONE_PATTERN.sub(_SAFE_PLACEHOLDER, result)
        result = _BEARER_PATTERN.sub(f"Bearer {_SAFE_PLACEHOLDER}", result)
        result = _JWT_PATTERN.sub(_SAFE_PLACEHOLDER, result)
        return result
    except Exception:
        logger.warning("mask_text failed, returning safe placeholder", exc_info=True)
        return _MASKING_FAILED


def mask_url(url: str) -> str:
    try:
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        parsed = urlparse(url)
        if not parsed.query:
            return url
        qs = parse_qs(parsed.query, keep_blank_values=True)
        masked_qs = {
            k: [_SAFE_PLACEHOLDER] if k.lower() in _URL_SENSITIVE_QUERY_KEYS else v
            for k, v in qs.items()
        }
        new_query = urlencode(masked_qs, doseq=True)
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
        )
    except Exception:
        logger.warning("mask_url failed, returning safe placeholder", exc_info=True)
        return _MASKING_FAILED
