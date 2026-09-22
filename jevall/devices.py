"""Torch device and dtype selection."""

from __future__ import annotations

from typing import Protocol

DEFAULT_DEVICE = "auto"
DEFAULT_DTYPE = "auto"
_DTYPES = ("bfloat16", "float16", "float32")


class TorchProbe(Protocol):
    """Minimal torch capability probe."""

    def cuda_available(self) -> bool:
        """Report whether CUDA is usable."""

    def mps_available(self) -> bool:
        """Report whether the Apple MPS backend is usable."""


class _RealProbe:
    def cuda_available(self) -> bool:
        import torch

        return bool(torch.cuda.is_available())

    def mps_available(self) -> bool:
        import torch

        backend = getattr(torch.backends, "mps", None)
        return bool(backend is not None and backend.is_available())


def resolve_device(
    requested: str | None,
    *,
    probe: TorchProbe | None = None,
) -> str:
    """Resolve `auto` to the best available device."""
    value = (requested or DEFAULT_DEVICE).strip().lower()
    active = probe or _RealProbe()
    if value == "auto":
        if active.cuda_available():
            return "cuda"
        if active.mps_available():
            return "mps"
        return "cpu"
    if value == "cuda" and not active.cuda_available():
        raise RuntimeError("device 'cuda' requested but CUDA is not available")
    return value


def resolve_dtype(requested: str | None, device: str) -> str:
    """Resolve `auto` to a dtype suited to the device."""
    value = (requested or DEFAULT_DTYPE).strip().lower()
    if value == "auto":
        if device == "cuda":
            return "bfloat16"
        if device == "mps":
            return "float16"
        return "float32"
    if value not in _DTYPES:
        raise ValueError(f"unsupported dtype: {value!r}")
    return value
