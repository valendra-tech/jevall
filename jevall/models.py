"""Model provisioning: resolve or download checkpoints before loading."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from typing import Any

from tqdm.auto import tqdm

from jevall.core import BackendUnavailableError

logger = logging.getLogger(__name__)

PROGRESS_INTERVAL_SECONDS = 5.0


def _human_bytes(value: float) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)}B"
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


class LogProgressBar(tqdm):
    """Progress reporter that logs throttled lines instead of drawing a bar.

    huggingface_hub subclasses the configured `tqdm_class`, so this must keep
    the full tqdm interface and only replace how progress is rendered.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("disable", False)
        self._last_log = time.monotonic()
        self._last_n: float | None = None
        super().__init__(*args, **kwargs)

    def display(self, msg: str | None = None, pos: int | None = None) -> None:
        del msg, pos
        self._log()

    def close(self) -> None:
        self._log(force=True)
        super().close()

    def _log(self, force: bool = False) -> None:
        if getattr(self, "disable", False):
            return
        now = time.monotonic()
        total = getattr(self, "total", None)
        current = float(getattr(self, "n", 0) or 0)
        if current <= 0 or self._last_n == current:
            return
        finished = bool(total) and current >= float(total)
        if (
            not force
            and not finished
            and now - self._last_log < PROGRESS_INTERVAL_SECONDS
        ):
            return
        self._last_log = now
        self._last_n = current
        started = getattr(self, "_start_t", self._last_log)
        elapsed = max(now - started, 1e-6)
        speed = current / elapsed
        if total:
            logger.info(
                "download %s: %s/%s (%.0f%%) %.1fMB/s",
                self.desc or "files",
                _human_bytes(current),
                _human_bytes(float(total)),
                100.0 * current / float(total),
                speed / (1024 * 1024),
            )
        else:
            logger.info(
                "download %s: %s %.1fMB/s",
                self.desc or "files",
                _human_bytes(current),
                speed / (1024 * 1024),
            )


def ensure_model(
    model_id: str,
    *,
    offline: bool | None = None,
    downloader: Callable[..., str] | None = None,
) -> str:
    """Return the local snapshot path, downloading it when missing."""
    if offline is None:
        offline = os.getenv("JEVALL_OFFLINE", "0") == "1"
    if offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    if downloader is None:
        try:
            from huggingface_hub import snapshot_download
        except ImportError as error:
            raise BackendUnavailableError(
                "model provisioning requires huggingface_hub"
            ) from error

        downloader = snapshot_download
    started = time.monotonic()
    logger.info("model.fetch id=%s offline=%s", model_id, offline)
    try:
        path = downloader(
            repo_id=model_id,
            local_files_only=offline,
            tqdm_class=LogProgressBar,
        )
    except Exception as error:
        logger.exception("model.fetch failed id=%s", model_id)
        raise BackendUnavailableError(f"could not fetch model {model_id!r}") from error
    logger.info(
        "model.ready id=%s path=%s elapsed=%.1fs",
        model_id,
        path,
        time.monotonic() - started,
    )
    return path
