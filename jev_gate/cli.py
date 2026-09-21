"""Command-line entry points for the local Jev Gate server."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Sequence

DEFAULT_MODEL = "demo"
DEFAULT_DEVICE = "cuda"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


def build_parser() -> argparse.ArgumentParser:
    """Build the `serve` argument parser."""
    parser = argparse.ArgumentParser(
        prog="serve",
        description="Run the Jev Gate decision gateway.",
    )
    parser.add_argument(
        "--model",
        help="model ID to serve, for example org/model (default: JEV_GATE_MODEL)",
    )
    parser.add_argument(
        "--device",
        help="torch device for the model backend (default: JEV_GATE_DEVICE)",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="bind port")
    return parser


def serve(
    argv: Sequence[str] | None = None,
    *,
    run: Callable[..., None] | None = None,
) -> None:
    """Run the FastAPI app with the selected model."""
    args = build_parser().parse_args(argv)
    os.environ["JEV_GATE_MODEL"] = (
        args.model or os.getenv("JEV_GATE_MODEL") or DEFAULT_MODEL
    )
    os.environ["JEV_GATE_DEVICE"] = (
        args.device or os.getenv("JEV_GATE_DEVICE") or DEFAULT_DEVICE
    )
    if run is None:
        import uvicorn

        run = uvicorn.run
    run("jev_gate.server:app", host=args.host, port=args.port)


if __name__ == "__main__":
    serve()
