"""Unit tests for sanitize_error_message — ensures no internals leak to client responses."""
from app.application.error_handling import SANITIZED_ERROR_MESSAGE, sanitize_error_message


def test_sanitize_generic_exception_returns_sanitized_constant():
    err = RuntimeError("boom — /etc/secrets/db.conf missing")
    result = sanitize_error_message(err)
    assert result == SANITIZED_ERROR_MESSAGE
    assert "/etc/secrets" not in result
    assert "boom" not in result


def test_sanitize_empty_message_exception():
    err = ValueError()
    result = sanitize_error_message(err)
    assert result == SANITIZED_ERROR_MESSAGE


def test_sanitize_does_not_leak_exception_type_name():
    class SuperSecretInternalError(Exception):
        pass

    result = sanitize_error_message(SuperSecretInternalError("oops"))
    assert result == SANITIZED_ERROR_MESSAGE
    assert "SuperSecretInternalError" not in result


def test_sanitize_handles_exception_with_request_attribute():
    from types import SimpleNamespace

    err = RuntimeError("upstream failure")
    err.request = SimpleNamespace(url=SimpleNamespace(path="/internal/admin"))

    result = sanitize_error_message(err)

    assert result == SANITIZED_ERROR_MESSAGE
    assert "/internal/admin" not in result
