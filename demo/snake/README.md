# JEVALL Snake Demo

This is a standalone reference demo for the JEVALL typed-decision gateway. It
is intentionally outside the gateway package: installing or deploying JEVALL
does not install Snake or its Rich terminal UI.

From the repository root:

```bash
uv sync --project demo/snake --extra dev
uv run --project demo/snake jevall-snake --url http://127.0.0.1:8000/v1/decisions
```

Run the demo tests and lint independently from this directory:

```bash
uv sync --extra dev
uv run --extra dev pytest -q
uv run --extra dev ruff check .
```

See the root README for the inference method and use-case mappings.
