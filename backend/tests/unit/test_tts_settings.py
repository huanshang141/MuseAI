from app.config.settings import Settings


class TestTTSSettings:
    def test_default_values(self):
        settings = Settings(
            JWT_SECRET="test-secret-that-is-long-enough-32chars",
            LLM_API_KEY="test-key",
            APP_ENV="development",
            TTS_API_KEY="",
            _env_file=None,
        )
        assert settings.TTS_ENABLED is True
        assert settings.TTS_PROVIDER == "xiaomi"
        assert settings.TTS_BASE_URL == "https://api.xiaomimimo.com/v1"
        assert settings.TTS_API_KEY == ""
        assert settings.TTS_MODEL == "mimo-v2.5-tts"
        assert settings.TTS_DEFAULT_VOICE == "冰糖"
        assert settings.TTS_TIMEOUT == 30.0
        assert settings.TTS_VOICE_DESIGN_MODEL == "mimo-v2.5-tts-voicedesign"

    def test_production_requires_tts_api_key_when_provider_set(self):
        try:
            Settings(
                JWT_SECRET="test-secret-that-is-long-enough-32chars",
                LLM_API_KEY="test-key",
                APP_ENV="production",
                TTS_PROVIDER="xiaomi",
                TTS_API_KEY="",
                CORS_ORIGINS="https://example.com",
            )
            assert False, "Should have raised"
        except ValueError as e:
            assert "TTS_API_KEY" in str(e)

    def test_production_allows_empty_tts_key_when_disabled(self):
        settings = Settings(
            JWT_SECRET="test-secret-that-is-long-enough-32chars",
            LLM_API_KEY="test-key",
            APP_ENV="production",
            TTS_ENABLED=False,
            TTS_PROVIDER="xiaomi",
            TTS_API_KEY="",
            CORS_ORIGINS="https://example.com",
        )
        assert settings.TTS_ENABLED is False

    def test_production_allows_empty_tts_key_when_mock(self):
        settings = Settings(
            JWT_SECRET="test-secret-that-is-long-enough-32chars",
            LLM_API_KEY="test-key",
            APP_ENV="production",
            TTS_PROVIDER="mock",
            TTS_API_KEY="",
            CORS_ORIGINS="https://example.com",
        )
        assert settings.TTS_PROVIDER == "mock"
