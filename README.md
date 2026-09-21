# Jev Gate

Jev Gate is a small, unofficial Jev-compatible gateway for typed decisions.
It exposes a FastAPI endpoint that turns model-specific inference into stable
`Choice`, `Score`, and `Noul` results.

The repository is intentionally closer to a small inference server than to a
production platform. It currently has no authentication, quotas, persistence,
job queue, or tenant isolation. The project is private while the API and model
adapter contract are being developed, with the goal of publishing it later.

## Status

The initial vertical includes:

- a Pydantic typed-decision contract;
- text-only and native `image`/`video` content-part schemas;
- an adapter protocol with a deterministic demo adapter;
- a FastAPI server with `/v1/decisions`, `/v1/models`, and `/health`;
- a `uv` development workflow and tests without model downloads.

The demo adapter is not an LLM. It makes the complete API runnable before the
Qwen 3.5 9B adapter and other providers are added.

This is not the official Jev implementation. It is an unofficial,
Jev-compatible contract and gateway.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)

## Development

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
```

Start the local server:

```bash
uv run uvicorn jev_gate.server:app --reload
```

Or use the installed command:

```bash
uv run jev-gate
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

## Before Publishing

This first scaffold is not safe to expose to untrusted traffic. Before changing
the GitHub repository to public, the project needs authentication and resource
limits, a validated media URI policy that prevents local-file and SSRF access,
bounded image/video processing, sanitized backend errors, and a dependency and
license review.

## Design

The approved design and implementation plan are in:

- `docs/superpowers/specs/2026-09-21-jev-gate-design.md`
- `docs/superpowers/plans/2026-09-21-jev-gate-initial-repository.md`

## License

Apache-2.0. See `LICENSE`.
