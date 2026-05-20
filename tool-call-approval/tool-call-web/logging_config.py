import logging
import sys

from pythonjsonlogger import jsonlogger


class _ServiceFilter(logging.Filter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service
        return True


def _make_handler(service: str) -> logging.StreamHandler:
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(service)s %(message)s",
        rename_fields={
            "levelname": "level",
            "asctime": "timestamp",
            "name": "logger",
        },
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(_ServiceFilter(service))
    return handler


def setup_logging(service: str) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(_make_handler(service))
    root.setLevel(logging.INFO)

    logging.getLogger("httpx").setLevel(logging.WARNING)


def reconfigure_uvicorn_loggers(service: str) -> None:
    """Replace uvicorn's plain-text handlers with JSON ones.

    Must be called from the app lifespan — uvicorn installs its own handlers
    after module import, so this has to run after uvicorn's logging setup.
    """
    handler = _make_handler(service)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        lgr = logging.getLogger(name)
        lgr.handlers.clear()
        lgr.addHandler(handler)
        lgr.setLevel(logging.INFO)
        lgr.propagate = False
