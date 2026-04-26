# backend/tests/unit/test_llm_trace_masking.py
from app.application.llm_trace.masking import mask_json, mask_text, mask_url


def test_mask_json_sensitive_keys():
    data = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "hello"}],
        "api_key": "sk-123456",
        "token": "abc",
        "nested": {"password": "secret", "value": 42},
    }
    result = mask_json(data)
    assert result["api_key"] == "[REDACTED]"
    assert result["token"] == "[REDACTED]"
    assert result["nested"]["password"] == "[REDACTED]"
    assert result["nested"]["value"] == 42
    assert result["model"] == "gpt-4"


def test_mask_json_preserves_usage_tokens():
    data = {
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }
    }
    result = mask_json(data)
    assert result["usage"]["prompt_tokens"] == 10
    assert result["usage"]["completion_tokens"] == 5
    assert result["usage"]["total_tokens"] == 15


def test_mask_json_redacts_access_token():
    data = {"access_token": "secret-token-value"}
    result = mask_json(data)
    assert result["access_token"] == "[REDACTED]"


def test_mask_json_redacts_api_key():
    data = {"api_key": "sk-abc123"}
    result = mask_json(data)
    assert result["api_key"] == "[REDACTED]"


def test_mask_json_email_in_string():
    data = {"message": "Contact me at user@example.com please"}
    result = mask_json(data)
    assert result["message"] == "Contact me at [REDACTED] please"


def test_mask_text_email():
    assert mask_text("Email: foo@bar.com") == "Email: [REDACTED]"


def test_mask_text_phone():
    assert mask_text("Call 13800138000") == "Call [REDACTED]"


def test_mask_text_bearer():
    assert mask_text("Authorization: Bearer abc123.def") == "Authorization: Bearer [REDACTED]"


def test_mask_text_jwt():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjMifQ.SflKxw"
    assert mask_text(f"Token {token}") == "Token [REDACTED]"


def test_mask_url_sensitive_query():
    url = "https://api.example.com/v1/chat?api_key=secret123&model=gpt-4"
    result = mask_url(url)
    assert "api_key=" in result
    assert "%5BREDACTED%5D" in result
    assert "model=gpt-4" in result


def test_mask_url_no_query():
    url = "https://api.example.com/v1/chat"
    assert mask_url(url) == url


def test_mask_json_failure_fallback():
    class Bad:
        def __getitem__(self, item):
            raise RuntimeError("boom")
        def keys(self):
            raise RuntimeError("boom")

    result = mask_json(Bad())
    assert result == "[MASKING_FAILED]"


def test_mask_text_failure_fallback():
    class BadStr:
        def __str__(self):
            return "x"

    result = mask_text(BadStr())
    assert result == "[MASKING_FAILED]"
