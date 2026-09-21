# JEVALL

JEVALL (Jev for All LLMs) is a small, unofficial Jev-compatible gateway for
typed decisions. It exposes a FastAPI endpoint that turns model-specific
inference into stable `Choice`, `Score`, and `Noul` results.

The repository is intentionally closer to a small inference server than to a
production platform. It currently has no authentication, quotas, persistence,
job queue, or tenant isolation. The project is private while the API and model
adapter contract are being developed, with the goal of publishing it later.

The project was previously named `jev-gate`; the package, CLI and environment
variables (`JEVALL_*`) were renamed, so old `JEV_GATE_*` variables no longer
apply.

## Status

The initial vertical includes:

- a Pydantic typed-decision contract;
- text-only and native `image`/`video` content-part schemas;
- an adapter protocol with a deterministic demo adapter;
- a FastAPI server with `/v1/decisions`, `/v1/models`, and `/health`;
- a `uv` development workflow and tests without model downloads.
- an optional Qwen 3.5 Transformers adapter for `Qwen/Qwen3.5-9B`.

The demo adapter is not an LLM. It makes the complete API runnable without
downloading a model. The Qwen adapter uses one independent batched backbone
forward for the request, manual projection over restricted existing-token
labels, and Qwen's native text/image/video processor inputs without generation.

This is not the official Jev implementation. It is an unofficial,
Jev-compatible contract and gateway.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)

The pinned Qwen runtime uses PyTorch 2.8 wheels and therefore requires Python
3.12 or 3.13 on the GPU host.

## Development

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
```

Install the Qwen runtime only on a compatible GPU host:

```bash
uv sync --extra dev --extra qwen
```

Start the server with a model:

```bash
uv run serve --model org/model
```

`serve` binds `0.0.0.0:8000` by default. Override with `--host` and `--port`,
pick the device with `--device` and the dtype with `--dtype`:

```bash
uv run serve --model Qwen/Qwen3.5-4B --device cuda --dtype bfloat16 --port 8000
```

`--device auto` (the default) resolves to `cuda`, then `mps`, then `cpu`, and
`--dtype auto` follows the device (`bfloat16`, `float16`, `float32`). Explicit
`--device cuda` fails fast when CUDA is unavailable.

Without `--model` it uses `JEVALL_MODEL`, and with neither it serves the
deterministic demo adapter.

### Model provisioning

The server downloads the checkpoint on first start, with throttled progress
lines such as `download model.safetensors: 2.1GB/4.7GB (45%) 38.0MB/s`, and
loads it from the local snapshot afterwards. Set `JEVALL_OFFLINE=1` on hosts
without network access to skip downloading and fail with a clear message when
the model is missing.

On a GPU host, sync the Qwen extra first, or keep the environment untouched with
`--no-sync` when the extra is already installed:

```bash
uv sync --extra qwen
uv run serve --model Qwen/Qwen3.5-4B

# or, without re-syncing:
uv run --no-sync serve --model Qwen/Qwen3.5-4B
```

The env-var form still works:

```bash
JEVALL_MODEL=Qwen/Qwen3.5-4B \
JEVALL_DEVICE=auto \
uv run uvicorn jevall.server:app --host 0.0.0.0 --port 8000
```

Or use the installed legacy command:

```bash
uv run jevall
```

## Logs

`serve` configures a single log format for the app and Uvicorn, at
`--log-level` / `JEVALL_LOG_LEVEL` (`info` by default). Startup logs cover model
fetch, load, warmup, batcher settings and the listening address; each decision
logs one line:

```
decision id=dec_… model=Qwen/Qwen3.5-4B questions=2 batch_rows=4 queue_ms=8.1 forward_ms=64.4 scoring_ms=0.7 total_ms=74.2 selected=['dhl', 'madrid']
```

`GET /health` reports `status`, `model`, `device`, `dtype` and `ready`.

## Micro-batching

The server merges concurrent requests into a single adapter forward pass. It is
enabled by default and controlled by environment variables:

- `JEVALL_BATCH_ENABLED` (`1`): set to `0` to bypass the batcher.
- `JEVALL_BATCH_WINDOW_MS` (`8`): collection window per batch.
- `JEVALL_BATCH_MAX_ROWS` (`32`): maximum question rows per batch.
- `JEVALL_REQUEST_TIMEOUT_MS` (`10000`): per-request queue deadline.
- `JEVALL_WARMUP` (`1`): compile backend kernels at startup.
- `JEVALL_WARMUP_ROWS` (`1,2,4,8,16,32`): row buckets compiled at startup;
  runtime batches are padded to these shapes so kernels never recompile.

Each response reports `queue_ms`, `forward_ms`, `scoring_ms`, and `batch_rows`
in `diagnostics`.

Install `flash-linear-attention` (included in the `qwen` extra) on the GPU host:
without it the 24 Qwen 3.5 GatedDeltaNet layers fall back to a slow fp32 torch
scan and latency grows roughly fivefold.

Measure latency with:

```bash
uv run python scripts/benchmark.py --levels 1,4,8,16 --requests 32
```

## API

`state` can be a text string for the simple case:

```json
{
  "model": "demo",
  "state": "A payment incident is under investigation.",
  "questions": [
    {
      "id": "team",
      "type": "choice",
      "prompt": "Which team should handle this?",
      "options": [
        {"id": "technical", "text": "Technical support"},
        {"id": "billing", "text": "Billing support"}
      ]
    }
  ]
}
```

For multimodal requests, use a list of content parts:

```json
{
  "model": "demo",
  "state": [
    {"type": "text", "text": "Review this checkout incident."},
    {"type": "image", "uri": "file:///tmp/screenshot.png"},
    {"type": "video", "uri": "file:///tmp/checkout.mp4"}
  ],
  "questions": [
    {
      "id": "severity",
      "type": "score",
      "prompt": "What is the incident severity?",
      "levels": ["low", "medium", "high", "critical"]
    },
    {
      "id": "refund_requested",
      "type": "noul",
      "prompt": "Did the customer explicitly request a refund?"
    }
  ]
}
```

The core preserves media parts and delegates their interpretation to the
selected adapter. The first Qwen adapter will use Qwen's native multimodal
processor rather than a gateway-owned frame extraction pipeline.

## Docker

Images are published to GHCR by `.github/workflows/ghcr.yaml` for two CUDA
majors:

| Variant  | Base image                                | Torch              |
| -------- | ----------------------------------------- | ------------------ |
| `cuda12` | `nvidia/cuda:12.8.1-runtime-ubuntu24.04`  | `2.8.0+cu128` (lock) |
| `cuda13` | `nvidia/cuda:13.0.3-runtime-ubuntu24.04`  | `2.9.1+cu130`      |

The `cuda13` image replaces the locked `torch`/`torchvision` wheels with the
CUDA 13 builds from the PyTorch index, because the lock pins the CUDA 12 wheel.

Build locally:

```bash
docker build -t jevall:cuda12 .

docker build -t jevall:cuda13 \
  --build-arg CUDA_VERSION=13.0.3 \
  --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu130 \
  --build-arg TORCH_SPEC="torch==2.9.1+cu130 torchvision==0.24.1+cu130" .
```

Run the deterministic demo adapter (no GPU needed):

```bash
docker run --rm -p 8000:8000 jevall:cuda12
```

Run a real model on the GPU:

```bash
docker run --rm --gpus all -p 8000:8000 -v jevall-models:/models \
  ghcr.io/valendra-tech/jevall:cuda12 --model Qwen/Qwen3.5-4B
```

The entrypoint is `serve`, so any `serve` flag can be appended. The model cache
lives in `/models` (`HF_HOME`); mount a volume to keep it between runs. The
image runs as root and serves on port 8000.

## Before Publishing

This first scaffold is not safe to expose to untrusted traffic. Before changing
the GitHub repository to public, the project needs authentication and resource
limits, a validated media URI policy that prevents local-file and SSRF access,
bounded image/video processing, sanitized backend errors, and a dependency and
license review.

## License

Apache-2.0. See `LICENSE`.
