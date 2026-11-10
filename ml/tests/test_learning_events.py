import json

import pytest

from neuroknot_ml.learning_events import EventValidationError, parse_event


def exposure(**overrides):
    return {
        "version": 1, "type": "exposure", "event_id": "e1", "user_id": "u1", "exposure_id": "x1",
        "occurred_at": "2026-01-05T00:00:00+09:00", "passage_id": "p1", "quiz_version": "quiz-v1",
        "item_ids": ["q1", "q2"], **overrides,
    }


def submission(**overrides):
    return {
        "version": 1, "type": "submission", "event_id": "e2", "user_id": "u1", "exposure_id": "x1",
        "occurred_at": "2026-01-05T00:01:00+09:00", "submission_id": "s1", "passage_id": "p1",
        "item_id": "q1", "item_version": "v1", "skill": "fact", "is_correct": True, "is_retry": False,
        **overrides,
    }


def completion(**overrides):
    return {
        "version": 1, "type": "completion", "event_id": "e3", "user_id": "u1", "exposure_id": "x1",
        "occurred_at": "2026-01-05T00:02:00+09:00", "status": "completed", **overrides,
    }


@pytest.mark.parametrize("payload", [exposure(), submission(), completion()])
def test_events_round_trip_through_strict_json(payload):
    event = parse_event(payload)
    normalized = json.loads(json.dumps(event.to_dict(), allow_nan=False))

    assert parse_event(normalized) == event
    assert normalized["occurred_at"].startswith("2026-01-04T15:")
    assert normalized["occurred_at"].endswith("Z")


@pytest.mark.parametrize(
    "overrides",
    [
        {"version": True}, {"version": 2}, {"type": "unknown"}, {"event_id": ""},
        {"user_id": " u1"}, {"item_ids": []}, {"item_ids": ["q1", "q1"]},
        {"occurred_at": "2026-01-05T00:00:00"}, {"occurred_at": "2026-02-30T00:00:00Z"},
        {"occurred_at": "2026-01-05T00:00:00+01:60"}, {"occurred_at": "2026-01-05"},
        {"answer_index": 1},
    ],
)
def test_invalid_exposure_payload_is_rejected(overrides):
    with pytest.raises(EventValidationError):
        parse_event(exposure(**overrides))


@pytest.mark.parametrize("overrides", [{"is_correct": 1}, {"is_retry": None}, {"hint_used": "yes"}, {"skill": "reading"}])
def test_invalid_submission_fields_are_rejected(overrides):
    with pytest.raises(EventValidationError):
        parse_event(submission(**overrides))


def test_missing_fields_and_invalid_completion_are_rejected():
    payload = submission()
    del payload["item_version"]
    with pytest.raises(EventValidationError, match="item_version"):
        parse_event(payload)
    with pytest.raises(EventValidationError, match="status"):
        parse_event(completion(status="pending"))
