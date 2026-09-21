# Jev Gate Initial Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first private, English-only Jev-compatible typed-decision gateway with a `uv` project, FastAPI server, adapter protocol, and deterministic test backend.

**Architecture:** Keep Pydantic schemas independent from the adapter protocol. The core resolves a model adapter and returns typed decisions without inspecting media; FastAPI only transports the public contract. The demo adapter provides a dependency-free model substitute so the full API is testable before the Qwen adapter is added.

**Tech Stack:** Python 3.12+, `uv`, Pydantic 2, FastAPI, Uvicorn, pytest, HTTPX, Ruff.

---

### Task 1: Create the package metadata and project documentation

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.gitignore`
- Create: `LICENSE`
- Create: `jev_gate/__init__.py`
- Create: `jev_gate/__main__.py`

- [ ] **Step 1: Add the `uv` project metadata**

Define a package named `jev-gate`, Python `>=3.12`, runtime dependencies `fastapi>=0.115`, `pydantic>=2.9`, and `uvicorn[standard]>=0.30`, plus a `dev` optional dependency group containing `httpx`, `pytest`, and `ruff`. Add a `jev-gate` script entry point targeting `jev_gate.__main__:main`.

- [ ] **Step 2: Add English README and repository policy files**

Document the unofficial Jev-compatible scope, `uv sync`, `uv run uvicorn jev_gate.server:app --reload`, the three endpoints, the string shorthand for `state`, and the current demo adapter limitation. Add an Apache-2.0 license and ignore `.venv`, caches, build output, and local model artifacts.

- [ ] **Step 3: Add package exports and the CLI entry point**

Export the version and public request/response types from `jev_gate.__init__`. Make `python -m jev_gate` call Uvicorn with `jev_gate.server:app`.

- [ ] **Step 4: Run the project bootstrap checks**

Run `uv sync --extra dev` and `uv run python -m compileall jev_gate`. Expected: dependency resolution succeeds and compileall exits with code 0.

### Task 2: Implement the typed Jev-compatible schemas

**Files:**
- Create: `jev_gate/schemas.py`
- Create: `tests/test_schemas.py`

- [ ] **Step 1: Write failing schema tests**

Cover string `state` normalization, content-part list validation, duplicate IDs, the three question types, and rejection of fewer than two choice options.

- [ ] **Step 2: Run the focused tests and verify they fail for missing schema code**

Run `uv run pytest tests/test_schemas.py -q`. Expected: collection fails because `jev_gate.schemas` does not yet exist.

- [ ] **Step 3: Implement minimal Pydantic models**

Add `TextPart`, `ImagePart`, `VideoPart`, a discriminated `ContentPart` union, `Option`, `ChoiceQuestion`, `ScoreQuestion`, `NoulQuestion`, `DecisionRequest`, `DecisionResult`, `DecisionResponse`, `ModelInfo`, and `Usage`. Use `state: str | list[ContentPart]` and a helper that normalizes a string to one `TextPart`.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run `uv run pytest tests/test_schemas.py -q`. Expected: all schema tests pass.

### Task 3: Implement the adapter protocol and core engine

**Files:**
- Create: `jev_gate/adapters/__init__.py`
- Create: `jev_gate/adapters/base.py`
- Create: `jev_gate/adapters/demo.py`
- Create: `jev_gate/core.py`
- Create: `tests/test_core.py`

- [ ] **Step 1: Write failing core tests**

Test model registration, unknown-model lookup, string-state normalization, one result per question, stable demo selections, and diagnostics containing the adapter name.

- [ ] **Step 2: Run the focused tests and verify the expected failure**

Run `uv run pytest tests/test_core.py -q`. Expected: collection fails because the core and adapter modules do not yet exist.

- [ ] **Step 3: Implement the adapter protocol and demo adapter**

Define an adapter protocol with `model_info` and `decide(request)`. Implement `DemoAdapter` with declared text/image/video capabilities. It must select the first choice option, first score level, and `False` for noul, with probabilities only where the deterministic result is meaningful.

- [ ] **Step 4: Implement `DecisionEngine`**

Store adapters by model ID, normalize request state before dispatch, enforce declared modality and decision-type capabilities, validate adapter result count/IDs/types/selections/probability keys, generate a UUID decision ID, measure elapsed milliseconds, and build a `DecisionResponse` with adapter diagnostics and nullable token usage.

- [ ] **Step 5: Run core tests and the complete test suite**

Run `uv run pytest tests/test_core.py -q` and then `uv run pytest -q`. Expected: focused tests and the full suite pass.

### Task 4: Add the FastAPI transport

**Files:**
- Create: `jev_gate/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing API tests**

Use `fastapi.testclient.TestClient` with an injected `DecisionEngine`. Test health, model listing, successful text-only decisions, list-form state, and unknown-model `404`.

- [ ] **Step 2: Run the API tests and verify the expected failure**

Run `uv run pytest tests/test_server.py -q`. Expected: collection fails because `jev_gate.server` does not yet exist.

- [ ] **Step 3: Implement `create_app` and the default app**

Create a FastAPI app factory accepting an engine, register `/health`, `/v1/models`, and `/v1/decisions`, translate request validation to `400`, unknown-model errors to `404`, unsupported capabilities to `422`, and unavailable backends to `503`, then instantiate a default app with the demo adapter.

- [ ] **Step 4: Run API tests and a local request smoke test**

Run `uv run pytest tests/test_server.py -q` and `uv run python -c "from fastapi.testclient import TestClient; from jev_gate.server import app; print(TestClient(app).get('/health').json())"`. Expected: tests pass and the command prints `{'status': 'ok'}`.

### Task 5: Add repository-level verification and publish the initial private commit

**Files:**
- Modify: `README.md`
- Create: `tests/test_imports.py`

- [ ] **Step 1: Add import and ASGI smoke coverage**

Verify that importing `jev_gate` does not import heavyweight model libraries and that the Uvicorn entry point is discoverable without a model download.

- [ ] **Step 2: Run all verification commands**

Run `uv run pytest -q`, `uv run ruff check .`, `uv run python -m compileall jev_gate`, and `git diff --check`. Expected: all commands exit 0 with no warnings caused by the repository.

- [ ] **Step 3: Inspect the final diff and status**

Run `git status --short`, `git diff --stat`, and `git diff --check`. Confirm that only the new repository files are present and no credentials, local model files, or environment files are included.

- [ ] **Step 4: Create and push the initial private commit**

Run:

```bash
git add .
git commit -m "feat: add Jev-compatible decision gateway"
git push -u origin main
```

Expected: the private `valendra-tech/jev-gate` repository contains the initial English `uv` project and its verified test suite.
