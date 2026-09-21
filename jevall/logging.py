"""Logging configuration for the server and CLI."""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
DEFAULT_LEVEL = "info"
QUIET_LOGGERS = ("httpx", "httpcore")


def configure_logging(level: str | None = None) -> None:
    """Configure root logging once for the process."""
    selected = (level or DEFAULT_LEVEL).upper()
    logging.basicConfig(
        level=getattr(logging, selected, logging.INFO),
        format=LOG_FORMAT,
        force=True,
    )
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
