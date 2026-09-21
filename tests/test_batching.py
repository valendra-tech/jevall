import asyncio

import pytest

from jevall.adapters.base import AdapterBatch
from jevall.batching import MicroBatcher, RequestTimeoutError
from jevall.core import BackendUnavailableError
from jevall.schemas import DecisionRequest, DecisionResult


def request(question_id: str = "team") -> DecisionRequest:
    return DecisionRequest.model_validate(
        {
            "model": "test",
            "state": "A payment incident is under investigation.",
            "questions": [
                {
                    "id": question_id,
                    "type": "choice",
                    "prompt": "Which team should handle this?",
                    "options": [
                        {"id": "technical", "text": "Technical support"},
                        {"id": "billing", "text": "Billing support"},
                    ],
                }
            ],
        }
    )


class RecordingAdapter:
    def __init__(self, *, delay=0.0, reject_batches=False, fail_ids=()):
        self.delay = delay
        self.reject_batches = reject_batches
        self.fail_ids = set(fail_ids)
        self.calls = []
        self.max_concurrent = 0
        self._concurrent = 0

    def decide_batch(self, requests):
        self._concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self._concurrent)
        self.calls.append(tuple(len(r.questions) for r in requests))
        try:
            if self.delay:
                import time

                time.sleep(self.delay)
            if self.reject_batches and len(requests) > 1:
                raise RuntimeError("batch rejected")
            decisions = []
            for current in requests:
                results = []
                for question in current.questions:
                    if question.id in self.fail_ids:
                        raise RuntimeError(f"row failed: {question.id}")
                    results.append(
                        DecisionResult(
                            id=question.id,
                            type=question.type,
                            selected=question.options[0].id,
                            probabilities={
                                option.id: float(
                                    option.id == question.options[0].id
                                )
                                for option in question.options
                            },
                        )
                    )
                decisions.append(tuple(results))
            return AdapterBatch(
                decisions=tuple(decisions),
                rows=sum(len(r.questions) for r in requests),
                forward_ms=1.0,
                scoring_ms=0.5,
            )
        finally:
            self._concurrent -= 1


def test_batcher_merges_concurrent_requests_into_one_call():
    adapter = RecordingAdapter(delay=0.05)
    batcher = MicroBatcher(window_ms=50, max_rows=8)

    async def run():
        return await asyncio.gather(
            batcher.submit(adapter, request("team")),
            batcher.submit(adapter, request("team-2")),
            batcher.submit(adapter, request("team-3")),
        )

    outcomes = asyncio.run(run())

    assert adapter.calls == [(1, 1, 1)]
    assert adapter.max_concurrent == 1
    assert [outcome.decisions[0].id for outcome in outcomes] == [
        "team",
        "team-2",
        "team-3",
    ]
    assert all(outcome.batch_rows == 3 for outcome in outcomes)
    assert all(outcome.queue_ms >= 0.0 for outcome in outcomes)
    assert all(outcome.forward_ms == 1.0 for outcome in outcomes)


def test_batcher_respects_max_rows():
    adapter = RecordingAdapter(delay=0.05)
    batcher = MicroBatcher(window_ms=50, max_rows=2)

    async def run():
        return await asyncio.gather(
            batcher.submit(adapter, request("team")),
            batcher.submit(adapter, request("team-2")),
            batcher.submit(adapter, request("team-3")),
        )

    outcomes = asyncio.run(run())

    assert adapter.calls == [(1, 1), (1,)]
    assert [outcome.decisions[0].id for outcome in outcomes] == [
        "team",
        "team-2",
        "team-3",
    ]


def test_batcher_expires_requests_past_their_deadline():
    adapter = RecordingAdapter()
    batcher = MicroBatcher(window_ms=50, timeout_ms=1)

    async def run():
        return await batcher.submit(adapter, request("team"))

    with pytest.raises(RequestTimeoutError):
        asyncio.run(run())

    assert adapter.calls == []


def test_batcher_retries_individually_after_batch_rejection():
    adapter = RecordingAdapter(reject_batches=True)
    batcher = MicroBatcher(window_ms=50, max_rows=8)

    async def run():
        return await asyncio.gather(
            batcher.submit(adapter, request("team")),
            batcher.submit(adapter, request("team-2")),
        )

    outcomes = asyncio.run(run())

    assert adapter.calls == [(1, 1), (1,), (1,)]
    assert [outcome.decisions[0].id for outcome in outcomes] == ["team", "team-2"]


def test_batcher_isolates_a_failing_row():
    adapter = RecordingAdapter(fail_ids=("team-2",))
    batcher = MicroBatcher(window_ms=50, max_rows=8)

    async def run():
        return await asyncio.gather(
            batcher.submit(adapter, request("team")),
            batcher.submit(adapter, request("team-2")),
            return_exceptions=True,
        )

    first, second = asyncio.run(run())

    assert first.decisions[0].id == "team"
    assert isinstance(second, BackendUnavailableError)


def test_batcher_rejects_invalid_max_rows():
    with pytest.raises(ValueError):
        MicroBatcher(max_rows=0)


def test_batcher_run_exclusive_serializes_with_batches():
    adapter = RecordingAdapter(delay=0.05)
    batcher = MicroBatcher(window_ms=10, max_rows=8)
    observed = []

    def probe():
        observed.append(adapter.max_concurrent)
        return "done"

    async def run():
        outcome = asyncio.create_task(batcher.submit(adapter, request("team")))
        await asyncio.sleep(0.01)
        result = await batcher.run_exclusive(probe)
        return await outcome, result

    outcome, result = asyncio.run(run())

    assert result == "done"
    assert observed == [0]
    assert outcome.decisions[0].id == "team"


def test_batcher_close_stops_accepting_work():
    batcher = MicroBatcher()
    batcher.close()

    with pytest.raises(BackendUnavailableError):
        asyncio.run(batcher.submit(RecordingAdapter(), request("team")))
