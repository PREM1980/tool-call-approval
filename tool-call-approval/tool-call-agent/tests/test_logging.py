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
    setup_logging("tool-calling-k8s-agent")
    logging.getLogger("test").info("hello world")
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["message"] == "hello world"
    assert record["level"] == "INFO"
    assert record["service"] == "tool-calling-k8s-agent"
    assert record["logger"] == "test"
    assert "timestamp" in record


def test_extra_fields_propagated(capsys):
    setup_logging("tool-calling-k8s-agent")
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


def test_reconfigure_uvicorn_loggers_replaces_handlers(capsys):
    reconfigure_uvicorn_loggers("tool-calling-k8s-agent")
    logging.getLogger("uvicorn.access").info("GET /health 200")
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["service"] == "tool-calling-k8s-agent"
    assert record["logger"] == "uvicorn.access"
    assert record["level"] == "INFO"


def test_reconfigure_uvicorn_loggers_disables_propagation():
    reconfigure_uvicorn_loggers("tool-calling-k8s-agent")
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        assert logging.getLogger(name).propagate is False
