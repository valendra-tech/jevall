# Jev Gate Initial Repository Design

**Status:** Approved for the initial repository scaffold

**Date:** 2026-09-21

## Goal

Create a small, unofficial Jev-compatible typed-decision gateway that can sit in
front of local and OpenAI-compatible language models. The first repository
vertical must be runnable with `uv`, expose a FastAPI surface, and keep the
model-specific implementation behind an adapter protocol.

## Product Direction

Jev Gate is intentionally closer to a small inference server than a production
platform. It does not include authentication, quotas, persistence, a job queue,
or operational policy in the first version. The repository is private initially
but should be written and structured for a future public release.

The project must not claim to be the official Jev implementation. Its public
language should describe the contract as Jev-compatible and unofficial.

## Public Contract

The primary endpoint is `POST /v1/decisions`.

- `model` selects a registered adapter.
- `state` accepts either a text string or a list of native content parts.
- Content parts support `text`, `image`, and `video`; the core preserves them and
  lets the selected adapter handle native media processing.
- `questions` contains typed `choice`, `score`, and `noul` decisions.
- Choice questions contain two to five stable options.
- Score questions contain two to five stable levels.
- Noul questions return a boolean selection.

The initial response contains a stable decision ID, typed decisions, optional
probabilities, usage, and adapter diagnostics. The gateway must never invent
probabilities when an adapter cannot provide them.

Supporting endpoints:

- `GET /v1/models` lists registered models and declared capabilities.
- `GET /health` reports process health.

The first version does not expose an OpenAI `chat/completions` compatibility
route. Typed decisions are the primary API; chat compatibility can be added as a
separate design later.

## Architecture

```text
jev_gate/
  schemas.py       Pydantic request and response contract
  core.py          adapter registry and decision orchestration
  adapters/
    base.py        adapter protocol and capability metadata
    demo.py        deterministic local adapter for examples and tests
    qwen35.py      Qwen 3.5 Transformers adapter with native media
  server.py        FastAPI application and routes
```

The core does not inspect or preprocess image/video data. Adapters receive the
normalized request and are responsible for converting content parts to the
backend's native format. A future Qwen 3.5 9B adapter will use the model's
native multimodal processor and will reuse the independent-question batching and
restricted candidate projection proven in the research probe.

The demo adapter is deliberately deterministic and is not presented as an LLM.
It makes the repository runnable and testable without downloading a model. The
Qwen adapter is an optional runtime dependency and performs one independent
batched model call per request, projecting only existing label tokens.

## Error Semantics

- `400`: malformed request data rejected by the API contract.
- `404`: requested model is not registered.
- `422`: adapter cannot support requested content or decision type.
- `503`: selected backend is unavailable.

## Non-Goals

- Authentication, rate limiting, billing, or tenant isolation.
- Persistent media storage or asynchronous video jobs.
- A provider-specific prompt format in the public schema.
- Fabricated confidence values or hidden fallback model calls.

## Publication Gate

The private scaffold must not be exposed to untrusted traffic until a future
publication pass adds authentication, request and media limits, an allowlisted
media URI policy, bounded image/video processing, sanitized backend errors, and
a dependency/license review. These controls are intentionally outside the
initial local inference vertical.

## Verification

The initial repository must verify:

- `state` string and content-list inputs normalize to the same internal shape.
- all three decision types validate and serialize correctly;
- duplicate question and option IDs are rejected;
- unknown models return `404`;
- the demo server handles a text-only request end to end;
- `uv run pytest`, `uv run ruff check .`, and `uv run python -m compileall`
  succeed.
