import json
import logging

from app.core.logging import configure_logging, get_logger, set_request_id


def test_log_record_is_json_with_request_id(capsys):
    configure_logging("DEBUG")
    set_request_id("req-123")
    logger = get_logger("test.logger")

    logger.info("hello")

    captured = json.loads(capsys.readouterr().out.strip())
    assert captured["message"] == "hello"
    assert captured["level"] == "INFO"
    assert captured["request_id"] == "req-123"


def test_configure_logging_respects_level(capsys):
    configure_logging("WARNING")
    logger = get_logger("test.logger.level")

    logger.info("should be filtered")

    assert capsys.readouterr().out == ""


def teardown_module():
    logging.getLogger().handlers.clear()
