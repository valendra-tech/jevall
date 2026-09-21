from jevall.adapters.demo import DemoAdapter
from jevall.schemas import DecisionRequest


def request(question_id: str = "team") -> DecisionRequest:
    return DecisionRequest.model_validate(
        {
            "model": "demo",
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


def test_demo_decide_batch_keeps_per_request_results():
    adapter = DemoAdapter()

    batch = adapter.decide_batch((request(), request("team-2")))

    assert batch.rows == 2
    assert [result.id for result in batch.decisions[0]] == ["team"]
    assert [result.id for result in batch.decisions[1]] == ["team-2"]
    assert batch.decisions[0][0].selected == "technical"
    assert batch.forward_ms == 0.0
    assert batch.scoring_ms == 0.0
