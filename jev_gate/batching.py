"""Single-flight micro-batching for GPU-backed decision adapters."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from time import perf_counter

from jev_gate.adapters.base import DecisionAdapter
from jev_gate.core import BackendUnavailableError
from jev_gate.schemas import DecisionRequest, DecisionResult


class RequestTimeoutError(BackendUnavailableError):
    """Raised when a queued request exceeds its deadline."""


@dataclass(frozen=True)
class BatchOutcome:
    """Per-request decisions plus timing diagnostics from one batch."""

    decisions: tuple[DecisionResult, ...]
    queue_ms: float
    forward_ms: float
    scoring_ms: float
    batch_rows: int


@dataclass
class _Job:
    adapter: DecisionAdapter
    request: DecisionRequest
    future: asyncio.Future
    enqueued_at: float
    deadline_at: float


class MicroBatcher:
    """Collect concurrent requests into single-flight adapter batches."""

    def __init__(
        self,
        *,
        window_ms: float = 8.0,
        max_rows: int = 32,
        timeout_ms: float = 10000.0,
        executor: ThreadPoolExecutor | None = None,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        if max_rows < 1:
            raise ValueError("max_rows must be at least 1")
        self.window_ms = window_ms
        self.max_rows = max_rows
        self.timeout_ms = timeout_ms
        self._clock = clock
        self._executor = executor or ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="jev-gate-gpu",
        )
        self._queue: asyncio.Queue[_Job] = asyncio.Queue()
        self._pending: deque[_Job] = deque()
        self._worker: asyncio.Task[None] | None = None

    async def submit(
        self,
        adapter: DecisionAdapter,
        request: DecisionRequest,
    ) -> BatchOutcome:
        loop = asyncio.get_running_loop()
        now = self._clock()
        job = _Job(
            adapter=adapter,
            request=request,
            future=loop.create_future(),
            enqueued_at=now,
            deadline_at=now + self.timeout_ms / 1000.0,
        )
        self._ensure_worker()
        self._queue.put_nowait(job)
        return await job.future

    async def run_exclusive(self, work, *args):
        """Run blocking backend work on the single GPU thread."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, work, *args)

    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.get_running_loop().create_task(self._run())

    async def _run(self) -> None:
        while True:
            batch, rows = await self._collect()
            await self._dispatch(batch, rows)

    async def _collect(self) -> tuple[list[_Job], int]:
        batch: list[_Job] = []
        rows = 0
        while self._pending:
            job = self._pending[0]
            job_rows = len(job.request.questions)
            if batch and rows + job_rows > self.max_rows:
                break
            self._pending.popleft()
            batch.append(job)
            rows += job_rows
        if not batch:
            job = await self._queue.get()
            batch.append(job)
            rows = len(job.request.questions)
        window_seconds = self.window_ms / 1000.0
        deadline = self._clock() + window_seconds
        while rows < self.max_rows:
            remaining = deadline - self._clock()
            if remaining <= 0:
                break
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=remaining)
            except TimeoutError:
                break
            job_rows = len(job.request.questions)
            if rows + job_rows > self.max_rows:
                self._pending.append(job)
                break
            batch.append(job)
            rows += job_rows
        return batch, rows

    async def _dispatch(self, batch: list[_Job], rows: int) -> None:
        started = self._clock()
        live: list[_Job] = []
        for job in batch:
            if job.deadline_at <= started:
                job.future.set_exception(
                    RequestTimeoutError("request expired before batch dispatch")
                )
            else:
                live.append(job)
        if not live:
            return
        loop = asyncio.get_running_loop()
        adapter = live[0].adapter
        requests = tuple(job.request for job in live)
        try:
            result = await loop.run_in_executor(
                self._executor,
                adapter.decide_batch,
                requests,
            )
        except Exception:
            await self._dispatch_individually(live, started)
            return
        for index, job in enumerate(live):
            job.future.set_result(
                self._outcome(
                    decisions=tuple(result.decisions[index]),
                    queue_ms=(started - job.enqueued_at) * 1000.0,
                    forward_ms=result.forward_ms,
                    scoring_ms=result.scoring_ms,
                    batch_rows=result.rows,
                )
            )

    async def _dispatch_individually(
        self,
        live: list[_Job],
        started: float,
    ) -> None:
        loop = asyncio.get_running_loop()
        for job in live:
            if job.deadline_at <= self._clock():
                job.future.set_exception(
                    RequestTimeoutError("request expired before retry")
                )
                continue
            try:
                result = await loop.run_in_executor(
                    self._executor,
                    job.adapter.decide_batch,
                    (job.request,),
                )
            except Exception as error:
                job.future.set_exception(
                    error
                    if isinstance(error, BackendUnavailableError)
                    else BackendUnavailableError(str(error))
                )
                continue
            job.future.set_result(
                self._outcome(
                    decisions=tuple(result.decisions[0]),
                    queue_ms=(started - job.enqueued_at) * 1000.0,
                    forward_ms=result.forward_ms,
                    scoring_ms=result.scoring_ms,
                    batch_rows=result.rows,
                )
            )

    @staticmethod
    def _outcome(
        *,
        decisions: tuple[DecisionResult, ...],
        queue_ms: float,
        forward_ms: float,
        scoring_ms: float,
        batch_rows: int,
    ) -> BatchOutcome:
        return BatchOutcome(
            decisions=decisions,
            queue_ms=queue_ms,
            forward_ms=forward_ms,
            scoring_ms=scoring_ms,
            batch_rows=batch_rows,
        )
