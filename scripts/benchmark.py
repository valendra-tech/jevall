#!/usr/bin/env python
"""Latency benchmark for the jevall decisions endpoint."""

from __future__ import annotations

import argparse
import asyncio
import time

import httpx

STATE = (
    "Order #4812 was delivered successfully on Tuesday. "
    "The carrier was DHL. The package was delivered to Madrid."
)
QUESTIONS = [
    {
        "id": "carrier",
        "type": "choice",
        "prompt": "Which carrier delivered the package?",
        "options": [
            {"id": "ups", "text": "UPS"},
            {"id": "dhl", "text": "DHL"},
            {"id": "fedex", "text": "FedEx"},
        ],
    },
    {
        "id": "destination",
        "type": "choice",
        "prompt": "Where was the package delivered?",
        "options": [
            {"id": "barcelona", "text": "Barcelona"},
            {"id": "madrid", "text": "Madrid"},
            {"id": "lisbon", "text": "Lisbon"},
        ],
    },
]


def payload(model: str) -> dict:
    return {"model": model, "state": STATE, "questions": QUESTIONS}


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(len(ordered) * fraction) - 1))
    return ordered[index]


async def measure(client, url, body, concurrency, total):
    semaphore = asyncio.Semaphore(concurrency)

    async def one():
        async with semaphore:
            started = time.perf_counter()
            response = await client.post(url, json=body)
            elapsed = (time.perf_counter() - started) * 1000.0
            response.raise_for_status()
            return elapsed, response.json()["usage"]["latency_ms"]

    return await asyncio.gather(*(one() for _ in range(total)), return_exceptions=True)


def report(concurrency: int, results) -> None:
    errors = [result for result in results if isinstance(result, Exception)]
    wall = [result[0] for result in results if not isinstance(result, Exception)]
    engine = [result[1] for result in results if not isinstance(result, Exception)]
    if not wall:
        print(f"conc={concurrency:2d} errors={len(errors)}")
        return
    print(
        f"conc={concurrency:2d} "
        f"wall p50={percentile(wall, 0.50):7.1f}ms "
        f"p95={percentile(wall, 0.95):7.1f}ms max={max(wall):7.1f}ms | "
        f"engine p50={percentile(engine, 0.50):7.1f}ms "
        f"p95={percentile(engine, 0.95):7.1f}ms | errors={len(errors)}"
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1/decisions")
    parser.add_argument("--model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--levels", default="1,4,8,16")
    parser.add_argument("--requests", type=int, default=32)
    args = parser.parse_args()

    levels = [int(level) for level in args.levels.split(",")]
    limits = httpx.Limits(
        max_connections=max(levels),
        max_keepalive_connections=max(levels),
    )
    async with httpx.AsyncClient(limits=limits, timeout=300.0) as client:
        await client.post(args.url, json=payload(args.model))
        for concurrency in levels:
            results = await measure(
                client,
                args.url,
                payload(args.model),
                concurrency,
                args.requests,
            )
            report(concurrency, results)


if __name__ == "__main__":
    asyncio.run(main())
