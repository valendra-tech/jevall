"""Command-line entry point for the local Jev Gate server."""

import uvicorn


def main() -> None:
    """Run the default FastAPI application."""
    uvicorn.run("jev_gate.server:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
