"""Tests for voice description helper functions."""

from app.application.tts_service import (
    VOICE_DESCRIPTION_KEY,
    extract_voice_description,
    store_voice_description,
)


class TestExtractVoiceDescription:
    def test_found(self):
        variables = [
            {"name": VOICE_DESCRIPTION_KEY, "description": "五十多岁的中年男性"},
            {"name": "other", "description": "something"},
        ]
        assert extract_voice_description(variables) == "五十多岁的中年男性"

    def test_not_found(self):
        variables = [{"name": "other", "description": "something"}]
        assert extract_voice_description(variables) is None

    def test_empty_variables(self):
        assert extract_voice_description([]) is None

    def test_empty_description(self):
        variables = [{"name": VOICE_DESCRIPTION_KEY, "description": ""}]
        assert extract_voice_description(variables) == ""


class TestStoreVoiceDescription:
    def test_new(self):
        existing = [{"name": "other", "description": "keep"}]
        result = store_voice_description(existing, "new voice")
        assert len(result) == 2
        assert result[0] == {"name": "other", "description": "keep"}
        assert result[1] == {"name": VOICE_DESCRIPTION_KEY, "description": "new voice"}

    def test_update(self):
        existing = [
            {"name": VOICE_DESCRIPTION_KEY, "description": "old"},
            {"name": "other", "description": "keep"},
        ]
        result = store_voice_description(existing, "updated voice")
        assert len(result) == 2
        voice_entry = [v for v in result if v["name"] == VOICE_DESCRIPTION_KEY]
        assert len(voice_entry) == 1
        assert voice_entry[0]["description"] == "updated voice"

    def test_clear(self):
        existing = [
            {"name": VOICE_DESCRIPTION_KEY, "description": "old"},
            {"name": "other", "description": "keep"},
        ]
        result = store_voice_description(existing, "")
        assert len(result) == 1
        assert result[0] == {"name": "other", "description": "keep"}

    def test_empty_existing(self):
        result = store_voice_description([], "new voice")
        assert result == [{"name": VOICE_DESCRIPTION_KEY, "description": "new voice"}]
