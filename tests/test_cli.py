import os

from jevall.cli import serve


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, app, **kwargs):
        self.calls.append((app, kwargs))


def test_serve_uses_the_model_flag(monkeypatch):
    monkeypatch.setenv("JEVALL_MODEL", "demo")
    monkeypatch.setenv("JEVALL_DEVICE", "cuda")
    runner = RecordingRunner()

    serve(["--model", "org/model"], run=runner)

    assert os.environ["JEVALL_MODEL"] == "org/model"
    assert os.environ["JEVALL_DEVICE"] == "cuda"
    assert runner.calls == [
        ("jevall.server:app", {"host": "0.0.0.0", "port": 8000})
    ]


def test_serve_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv("JEVALL_MODEL", "env/model")
    monkeypatch.setenv("JEVALL_DEVICE", "cpu")
    runner = RecordingRunner()

    serve([], run=runner)

    assert os.environ["JEVALL_MODEL"] == "env/model"
    assert os.environ["JEVALL_DEVICE"] == "cpu"
    assert runner.calls == [
        ("jevall.server:app", {"host": "0.0.0.0", "port": 8000})
    ]


def test_serve_honors_host_port_and_device_flags(monkeypatch):
    monkeypatch.setenv("JEVALL_MODEL", "demo")
    monkeypatch.setenv("JEVALL_DEVICE", "cuda")
    runner = RecordingRunner()

    serve(
        [
            "--model",
            "org/model",
            "--device",
            "cpu",
            "--host",
            "127.0.0.1",
            "--port",
            "9001",
        ],
        run=runner,
    )

    assert os.environ["JEVALL_DEVICE"] == "cpu"
    assert runner.calls == [
        ("jevall.server:app", {"host": "127.0.0.1", "port": 9001})
    ]


def test_serve_defaults_to_the_demo_model(monkeypatch):
    monkeypatch.delenv("JEVALL_MODEL", raising=False)
    monkeypatch.delenv("JEVALL_DEVICE", raising=False)
    runner = RecordingRunner()

    serve([], run=runner)

    assert os.environ["JEVALL_MODEL"] == "demo"
    assert os.environ["JEVALL_DEVICE"] == "cuda"
