import logging

import pytest

from jevall.core import BackendUnavailableError
from jevall.models import LogProgressBar, ensure_model


def test_ensure_model_returns_the_downloaded_snapshot(monkeypatch, caplog):
    calls = []

    def downloader(**kwargs):
        calls.append(kwargs)
        return "/cache/models--org--model/snapshots/abc"

    with caplog.at_level(logging.INFO, logger="jevall.models"):
        path = ensure_model("org/model", downloader=downloader)

    assert path == "/cache/models--org--model/snapshots/abc"
    assert calls[0]["repo_id"] == "org/model"
    assert calls[0]["local_files_only"] is False
    assert calls[0]["tqdm_class"] is LogProgressBar
    assert "model.fetch id=org/model" in caplog.text
    assert "model.ready id=org/model" in caplog.text


def test_ensure_model_maps_download_failures():
    def downloader(**kwargs):
        raise OSError("network down")

    with pytest.raises(BackendUnavailableError, match="could not fetch model"):
        ensure_model("org/model", downloader=downloader)


def test_ensure_model_offline_skips_downloading(monkeypatch):
    calls = []

    def downloader(**kwargs):
        calls.append(kwargs)
        return "/cache/snapshot"

    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    ensure_model("org/model", offline=True, downloader=downloader)

    assert calls[0]["local_files_only"] is True


def test_log_progress_bar_logs_throttled_lines(caplog):
    bar = LogProgressBar(total=1024 * 1024, desc="shard-1", disable=False)

    with caplog.at_level(logging.INFO, logger="jevall.models"):
        bar.update(512 * 1024)
        bar.close()

    lines = [line for line in caplog.text.splitlines() if "download shard-1" in line]
    assert len(lines) == 1
    assert "50%" in lines[0]


def test_log_progress_bar_can_be_disabled(caplog):
    bar = LogProgressBar(total=10, desc="shard-1", disable=True)

    with caplog.at_level(logging.INFO, logger="jevall.models"):
        bar.update(10)
        bar.close()

    assert "download shard-1" not in caplog.text
