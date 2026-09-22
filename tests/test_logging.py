import logging

from jevall.logging import configure_logging


def test_configure_logging_sets_level_and_format():
    configure_logging("debug")

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    handler = root.handlers[0]
    assert handler.formatter._fmt == (
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )


def test_configure_logging_defaults_to_info():
    configure_logging()

    assert logging.getLogger().level == logging.INFO


def test_configure_logging_quiets_http_clients():
    configure_logging("debug")

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
