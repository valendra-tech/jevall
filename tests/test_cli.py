import os

from jev_gate.cli import serve


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, app, **kwargs):
        self.calls.append((app, kwargs))


def test_serve_uses_the_model_flag(monkeypatch):
    monkeypatch.setenv("JEV_GATE_MODEL", "demo")
    monkeypatch.setenv("JEV_GATE_DEVICE", "cuda")
    runner = RecordingRunner()

    serve(["--model", "org/model"], run=runner)

    assert os.environ["JEV_GATE_MODEL"] == "org/model"
    assert os.environ["JEV_GATE_DEVICE"] == "cuda"
    assert runner.calls == [
        ("jev_gate.server:app", {"host": "0.0.0.0", "port": 8000})
    ]


def test_serve_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv("JEV_GATE_MODEL", "env/model")
    monkeypatch.setenv("JEV_GATE_DEVICE", "cpu")
    runner = RecordingRunner()

    serve([], run=runner)

    assert os.environ["JEV_GATE_MODEL"] == "env/model"
    assert os.environ["JEV_GATE_DEVICE"] == "cpu"
    assert runner.calls == [
        ("jev_gate.server:app", {"host": "0.0.0.0", "port": 8000})
    ]


def test_serve_honors_host_port_and_device_flags(monkeypatch):
    monkeypatch.setenv("JEV_GATE_MODEL", "demo")
    monkeypatch.setenv("JEV_GATE_DEVICE", "cuda")
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

    assert os.environ["JEV_GATE_DEVICE"] == "cpu"
    assert runner.calls == [
        ("jev_gate.server:app", {"host": "127.0.0.1", "port": 9001})
    ]


def test_serve_defaults_to_the_demo_model(monkeypatch):
    monkeypatch.delenv("JEV_GATE_MODEL", raising=False)
    monkeypatch.delenv("JEV_GATE_DEVICE", raising=False)
    runner = RecordingRunner()

    serve([], run=runner)

    assert os.environ["JEV_GATE_MODEL"] == "demo"
    assert os.environ["JEV_GATE_DEVICE"] == "cuda"
