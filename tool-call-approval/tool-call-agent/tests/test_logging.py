import json
import logging

import pytest

from logging_config import setup_logging


@pytest.fixture(autouse=True)
def reset_root_logger():
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_filters = root.filters[:]
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.filters = original_filters
    root.level = original_level


def test_log_output_is_valid_json(capsys):
    setup_logging("tool-call-agent")
    logging.getLogger("test").info("hello world")
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["message"] == "hello world"
    assert record["level"] == "INFO"
    assert record["service"] == "tool-call-agent"
    assert record["logger"] == "test"
    assert "timestamp" in record


def test_extra_fields_propagated(capsys):
    setup_logging("tool-call-agent")
    logging.getLogger("test").info("session started", extra={"session_id": "abc-123"})
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["session_id"] == "abc-123"


def test_service_label_customisable(capsys):
    setup_logging("my-service")
    logging.getLogger("test").info("msg")
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["service"] == "my-service"
