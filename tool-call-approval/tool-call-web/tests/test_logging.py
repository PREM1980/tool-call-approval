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
    setup_logging("tool-call-web")
    logging.getLogger("test").info("request proxied")
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["message"] == "request proxied"
    assert record["level"] == "INFO"
    assert record["service"] == "tool-call-web"
    assert record["logger"] == "test"
    assert "timestamp" in record


def test_extra_fields_propagated(capsys):
    setup_logging("tool-call-web")
    logging.getLogger("test").warning("backend error", extra={"status_code": 502})
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["status_code"] == 502
    assert record["level"] == "WARNING"
