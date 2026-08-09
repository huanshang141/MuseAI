from io import StringIO

from app.observability.logging import _text_format
from loguru import logger


def test_text_formatter_preserves_dict_braces_in_tts_debug_message():
    sink = StringIO()
    handler_id = logger.add(
        sink,
        format=_text_format,
        level="DEBUG",
        colorize=False,
        enqueue=False,
        catch=False,
    )
    try:
        logger.debug(
            "TTS prompt found: key={}, variables={}",
            "tour_tts_persona_a",
            [{"name": "__voice__", "description": "冰糖"}],
        )
        logger.debug("next record")
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "{'name': '__voice__', 'description': '冰糖'}" in output
    assert "next record" in output
    assert len(output.splitlines()) == 2
