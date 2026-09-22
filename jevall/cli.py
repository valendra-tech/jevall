"""Command-line entry points for the local JEVALL server."""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Callable, Sequence

from jevall.devices import DEFAULT_DEVICE, DEFAULT_DTYPE
from jevall.logging import configure_logging

DEFAULT_MODEL = "demo"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_LOG_LEVEL = "info"

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the `serve` argument parser."""
    parser = argparse.ArgumentParser(
        prog="serve",
        description="Run the JEVALL decision gateway.",
    )
    parser.add_argument(
        "--model",
        help="model ID to serve, for example org/model (default: JEVALL_MODEL)",
    )
    parser.add_argument(
        "--device",
        help=(
            "torch device: auto, cuda, mps or cpu "
            f"(default: {DEFAULT_DEVICE})"
        ),
    )
    parser.add_argument(
        "--dtype",
        help=(
            "model dtype: auto, bfloat16, float16 or float32 "
            f"(default: {DEFAULT_DTYPE})"
        ),
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="bind port")
    parser.add_argument(
        "--log-level",
        default=os.getenv("JEVALL_LOG_LEVEL", DEFAULT_LOG_LEVEL),
        help="log level (default: JEVALL_LOG_LEVEL or info)",
    )
    return parser


def serve(
    argv: Sequence[str] | None = None,
    *,
    run: Callable[..., None] | None = None,
) -> None:
    """Run the FastAPI app with the selected model."""
    args = build_parser().parse_args(argv)
    model = args.model or os.getenv("JEVALL_MODEL") or DEFAULT_MODEL
    device = args.device or os.getenv("JEVALL_DEVICE") or DEFAULT_DEVICE
    dtype = args.dtype or os.getenv("JEVALL_DTYPE") or DEFAULT_DTYPE
    os.environ["JEVALL_MODEL"] = model
    os.environ["JEVALL_DEVICE"] = device
    os.environ["JEVALL_DTYPE"] = dtype
    if run is None:
        configure_logging(args.log_level)
        import uvicorn

        run = uvicorn.run
    logger.info(
        "serve.start model=%s device=%s dtype=%s host=%s port=%s",
        model,
        device,
        dtype,
        args.host,
        args.port,
    )
    run(
        "jevall.server:app",
        host=args.host,
        port=args.port,
        log_config=None,
    )


if __name__ == "__main__":
    serve()
