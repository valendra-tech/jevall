# JEVALL

**Typed decisions from multimodal models, without token-by-token generation.**

JEVALL is an inference gateway for applications that need reliable,
machine-readable decisions from a language model. Each request combines the
current state with explicit typed questions; the response contains stable
selections, scores, booleans, probabilities and latency diagnostics.

The result is a focused, composable decision service for controlled production
workloads: one API contract for text, images and video; one adapter boundary for
local models; and operational features for batching, provisioning, health checks
and GPU containers.

## Inference method

JEVALL turns a generative language model into a constrained decision engine:

```text
state + typed questions
        |
        v
normalized multimodal prompt rows
        |
        v
one batched Qwen backbone forward pass
        |
        v
candidate-label logit projection
        |
        v
softmax over the valid labels only
        |
        v
typed decisions + probabilities + diagnostics
```

For each question, the adapter:

1. Converts the contract into a bounded answer set: 2 to 5 labels for `choice`
   and `score`, or `False`/`True` for `noul`.
2. Sends the text and native media parts through the model processor. Images and
   videos are interpreted by the model's multimodal path rather than by a
   gateway-owned frame extraction pipeline.
3. Runs the backbone once for every question row in the micro-batch. JEVALL does
   not autoregressively generate an answer string.
4. Resolves existing single-token answer labels in the tokenizer, reads the
   hidden state at the answer boundary, and scores only the corresponding rows
   of the model output embedding.
5. Applies softmax to those candidate logits, returns the winning label and the
   complete normalized probability map, and maps it back to the public typed
   contract.

### Why this works

Language models already represent next-token likelihoods in their output head.
When the valid answers are known in advance, the decision is a classification
problem over a small, explicit label set. Restricting inference to those labels
removes free-form text generation, invalid answers, parser failures, repetition
and variable output lengths while preserving the model's learned ranking.

The method is efficient because all questions in a batch share one backbone
forward pass. It is observable because the API returns probabilities and timing
breakdowns instead of an opaque generated string. It is multimodal because the
same contract preserves native `image` and `video` parts for the selected model.

### Why this is optimal for the contract

For a fixed model state and a fixed set of allowed labels, selecting the maximum
candidate logit is the exact argmax decision, and softmax over the same candidate
logits is the exact normalized distribution induced by the model's output head.
There is no approximation from decoding, sampling or post-hoc text parsing.

That claim is deliberately scoped: it means optimal inference for this bounded
decision interface, not a guarantee that every model is perfectly calibrated or
that the model's judgment is universally correct. Decision quality still depends
on the checkpoint, prompt, state representation and adapter.

The gateway is intended for private or controlled production environments;
authentication, quotas, persistence, tenant isolation and public media-URI policy
belong at the deployment boundary.

## What it does

- A Pydantic typed-decision contract: `choice`, `score` and `noul` questions
  answered with a selected label plus probabilities.
- Text or native `image`/`video` content parts in `state`; media is handed to
  the adapter untouched.
- An adapter protocol with a deterministic `demo` adapter that makes the whole
  API runnable without downloading a model.
- A Qwen 3.5 Transformers adapter that scores every question with one batched
  backbone forward and the constrained candidate-label projection described
  above.
- Single-flight micro-batching, so concurrent HTTP requests share one forward
  pass and two backend calls can never overlap.
- Automatic model provisioning (download on first start, cached afterwards),
  automatic device and dtype selection, and structured logs.
- CUDA 12 and CUDA 13 container images published to GHCR with a smoke test.
- Standalone reference demos kept outside the gateway package and its wheel.
- A latency benchmark script and a test suite that needs no model downloads.

## Use cases

A reference UI can make probabilities, latency and safety interventions visible
in real time. The gateway itself is domain-agnostic: an integration supplies a
state and a small set of typed questions, then receives stable decisions that
can route work, gate actions or feed another service.

The same contract supports workflows such as:

| Workflow | `choice` | `score` | `noul` |
| -------- | -------- | ------- | ------ |
| Customer support | queue or owner | urgency | refund requested |
| Incident response | team or runbook | severity | customer impact |
| Document and image review | document or defect class | condition or risk | required field present |
| Content moderation | moderation action | policy severity | policy violation |
| Claims and invoice processing | next review path | anomaly level | duplicate or evidence present |
| Agent and workflow routing | next tool or action | execution risk | approval required |

These are contract examples, not separate built-in applications. The value is
that each workflow uses the same constrained inference path, probability format,
batching, diagnostics and adapter boundary. Adding a new workflow usually means
defining its state, prompts and allowed labels rather than writing a new model
server.

## Repository layout

| Path                             | Contents                                        |
| -------------------------------- | ----------------------------------------------- |
| `jevall/`                        | Gateway package (server, engine, schemas, CLI)   |
| `jevall/adapters/`               | Adapter protocol, demo adapter, Qwen 3.5 adapter |
| `jevall/batching.py`             | Single-flight micro-batcher                      |
| `jevall/models.py`               | Model provisioning with progress logs            |
| `jevall/devices.py`              | Device and dtype resolution                      |
| `demo/`                          | Standalone reference demos with their own projects |
| `tests/`                         | Gateway pytest suite (65 tests, no GPU required) |
| `scripts/benchmark.py`           | Concurrency and latency benchmark                |
| `Dockerfile`                     | Multi-CUDA image with `CUDA_VERSION` build arg   |
| `.github/workflows/ghcr.yaml`    | Build, push and smoke-test both image variants   |

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

Standalone demos live under `demo/` and keep their dependencies, tests and
commands outside the gateway environment.

## Running

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
`--device cuda` fails fast when CUDA is unavailable. Without `--model` the
server uses `JEVALL_MODEL`, and with neither it serves the deterministic demo
adapter.

On a GPU host, sync the Qwen extra first, or keep the environment untouched with
`--no-sync` when the extra is already installed:

```bash
uv sync --extra qwen
uv run serve --model Qwen/Qwen3.5-4B

# or, without re-syncing:
uv run --no-sync serve --model Qwen/Qwen3.5-4B
```

The env-var form still works, as does the legacy `jevall` command:

```bash
JEVALL_MODEL=Qwen/Qwen3.5-4B JEVALL_DEVICE=auto \
  uv run uvicorn jevall.server:app --host 0.0.0.0 --port 8000
```

### Model provisioning

The server downloads the checkpoint on first start, with throttled progress
lines such as `download model.safetensors: 2.1GB/4.7GB (45%) 38.0MB/s`, and
loads it from the local snapshot afterwards. Set `JEVALL_OFFLINE=1` on hosts
without network access to skip downloading and fail with a clear message when
the model is missing.

### Logs

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

Each response reports `queue_ms`, `forward_ms`, `scoring_ms` and `batch_rows` in
`diagnostics`. Only one batch is in flight at a time; the next one starts as soon
as the previous one finishes.

Install `flash-linear-attention` (included in the `qwen` extra) on the GPU host:
without it the 24 Qwen 3.5 GatedDeltaNet layers fall back to a slow fp32 torch
scan and latency grows roughly fivefold.

Measured on an RTX 5090 with `Qwen/Qwen3.5-4B` and a two-question text payload
(32 requests per level, `scripts/benchmark.py`):

| Concurrency | p50 | p95 | Errors |
| ----------- | --- | --- | ------ |
| 1           | 49 ms  | 50 ms  | 0 |
| 4           | 63 ms  | 64 ms  | 0 |
| 8           | 96 ms  | 97 ms  | 0 |
| 16          | 103 ms | 266 ms | 0 |

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
selected adapter. The Qwen adapter feeds them to Qwen's native multimodal
processor instead of a gateway-owned frame extraction pipeline, and the
checkpoint can be any Qwen 3.5 multimodal model (`Qwen/Qwen3.5-4B` is the one
used for the measurements above).

## Docker

Images are published to GHCR by `.github/workflows/ghcr.yaml` for two CUDA
majors:

| Variant  | Base image                                | Torch              |
| -------- | ----------------------------------------- | ------------------ |
| `cuda12` | `nvidia/cuda:12.8.1-runtime-ubuntu24.04`  | `2.8.0+cu128` (lock) |
| `cuda13` | `nvidia/cuda:13.0.3-runtime-ubuntu24.04`  | `2.9.1+cu130`      |

The `cuda13` image replaces the locked `torch`/`torchvision` wheels with the
CUDA 13 builds from the PyTorch index, because the lock pins the CUDA 12 wheel.
Every build runs a smoke test: the image starts with `--model demo` and must
answer `/health`.

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

## License

Apache-2.0. See `LICENSE`.
