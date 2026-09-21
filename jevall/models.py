"""Model provisioning: resolve or download checkpoints before loading."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from typing import Any

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


class LogProgressBar:
    """Progress reporter that logs throttled single lines instead of bars."""

    def __init__(
        self,
        *,
        total: float | None = None,
        desc: str | None = None,
        disable: bool = False,
        **_: Any,
    ) -> None:
        self.total = total
        self.desc = desc or "files"
        self.n = 0.0
        self.disable = disable
        self._started = time.monotonic()
        self._last_log = self._started

    def update(self, n: float = 1) -> None:
        self.n += n
        self.display()

    def display(self, force: bool = False) -> None:
        if self.disable:
            return
        now = time.monotonic()
        if not force and now - self._last_log < PROGRESS_INTERVAL_SECONDS:
            return
        if not force and self.total and self.n >= self.total:
            force = True
        self._last_log = now
        elapsed = max(now - self._started, 1e-6)
        speed = self.n / elapsed
        if self.total:
            logger.info(
                "download %s: %s/%s (%.0f%%) %.1fMB/s",
                self.desc,
                _human_bytes(self.n),
                _human_bytes(self.total),
                100.0 * self.n / self.total,
                speed / (1024 * 1024),
            )
        else:
            logger.info(
                "download %s: %s %.1fMB/s",
                self.desc,
                _human_bytes(self.n),
                speed / (1024 * 1024),
            )

    def close(self) -> None:
        self.display(force=True)

    def __enter__(self) -> LogProgressBar:
        return self

    def __exit__(self, *_: Any) -> bool:
        self.close()
        return False


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
        raise BackendUnavailableError(f"could not fetch model {model_id!r}") from error
    logger.info(
        "model.ready id=%s path=%s elapsed=%.1fs",
        model_id,
        path,
        time.monotonic() - started,
    )
    return path
