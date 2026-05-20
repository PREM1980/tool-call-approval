import json
import logging

import pytest

from logging_config import reconfigure_uvicorn_loggers, setup_logging


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


def test_reconfigure_uvicorn_loggers_replaces_handlers(capsys):
    reconfigure_uvicorn_loggers("tool-call-web")
    logging.getLogger("uvicorn.access").info("GET /api/sessions 200")
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["service"] == "tool-call-web"
    assert record["logger"] == "uvicorn.access"


def test_reconfigure_uvicorn_loggers_disables_propagation():
    reconfigure_uvicorn_loggers("tool-call-web")
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        assert logging.getLogger(name).propagate is False
