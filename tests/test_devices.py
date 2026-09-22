import pytest

from jevall.devices import resolve_device, resolve_dtype


class Probe:
    def __init__(self, *, cuda=False, mps=False):
        self.cuda = cuda
        self.mps = mps

    def cuda_available(self):
        return self.cuda

    def mps_available(self):
        return self.mps


def test_auto_prefers_cuda():
    assert resolve_device("auto", probe=Probe(cuda=True, mps=True)) == "cuda"


def test_auto_falls_back_to_mps():
    assert resolve_device("auto", probe=Probe(mps=True)) == "mps"


def test_auto_falls_back_to_cpu():
    assert resolve_device("auto", probe=Probe()) == "cpu"


def test_explicit_device_passes_through():
    assert resolve_device("cpu", probe=Probe(cuda=True)) == "cpu"


def test_explicit_cuda_fails_without_cuda():
    with pytest.raises(RuntimeError, match="CUDA is not available"):
        resolve_device("cuda", probe=Probe())


def test_dtype_follows_the_device():
    assert resolve_dtype("auto", "cuda") == "bfloat16"
    assert resolve_dtype("auto", "mps") == "float16"
    assert resolve_dtype("auto", "cpu") == "float32"


def test_dtype_override_is_honored():
    assert resolve_dtype("float16", "cuda") == "float16"


def test_unknown_dtype_is_rejected():
    with pytest.raises(ValueError, match="unsupported dtype"):
        resolve_dtype("int8", "cuda")
