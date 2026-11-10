import pytest

from neuroknot_ml.learning_analytics import analyze_user
from neuroknot_ml.learning_events import EventValidationError
from neuroknot_ml.learning_history import CatalogItem, EventConflictError, LearningHistory
from test_learning_events import completion, exposure, submission

ITEMS = (CatalogItem("q1", "v1", "fact"), CatalogItem("q2", "v1", "fact"))
AT = "2026-01-05T00:00:00Z"


def envelope(sequence, event, applied_at=AT):
    return {"sequence": str(sequence), "applied_at": applied_at, "event": event}


def test_sequence_replays_shuffled_simultaneous_answers_with_shared_difficulty():
    events = [
        exposure(item_ids=["q1"], occurred_at=AT),
        exposure(event_id="u2-ex", exposure_id="x2", user_id="u2", item_ids=["q1"], occurred_at=AT),
        submission(occurred_at=AT),
        submission(event_id="u2-a", submission_id="s2", exposure_id="x2", user_id="u2",
                   occurred_at=AT, is_correct=False),
    ]
    online = LearningHistory(ITEMS)
    for event in events:
        online.accept_event(event, applied_at=AT)
    replayed = LearningHistory.replay_envelopes(ITEMS, reversed(online.event_log()))

    assert replayed.records == online.records
    assert replayed.event_log() == online.event_log()
    first, second = (record.attempt for record in replayed.records[-2:])
    assert second.difficulty_before == first.difficulty_after
    assert second.probability > first.probability
    assert replayed.item_difficulty("q1") == online.item_difficulty("q1")


def test_sequence_rejects_gaps_rebinding_and_clock_regression_without_consuming_position():
    history = LearningHistory(ITEMS)
    first = exposure(item_ids=["q1"], occurred_at=AT)
    answer = submission(occurred_at=AT)
    with pytest.raises(EventValidationError, match="missing sequence"):
        history.apply_envelope(envelope(2, first))
    original = history.apply_envelope(envelope(1, first, "2026-01-05T01:00:00Z"))
    assert history.apply_envelope(envelope(1, first, "2026-01-05T01:00:00Z")) == original
    with pytest.raises(EventConflictError, match="sequence"):
        history.apply_envelope(envelope(1, answer))
    with pytest.raises(EventConflictError, match="event_id"):
        history.apply_envelope(envelope(2, first))
    with pytest.raises(EventValidationError, match="nondecreasing"):
        history.apply_envelope(envelope(2, answer))
    assert history.apply_envelope(envelope(2, answer, "2026-01-05T01:00:00Z")).sequence == 2


def test_late_activity_is_grouped_by_seoul_date_but_theta_uses_application_time():
    sunday = "2026-01-04T14:59:59Z"
    monday = "2026-01-04T15:00:00Z"
    after_midnight = "2026-01-04T15:10:00Z"
    events = [
        envelope(1, exposure(item_ids=["q1", "q2"], occurred_at=sunday), sunday),
        envelope(2, submission(item_id="q2", event_id="a2", submission_id="s2", occurred_at=monday), monday),
        envelope(3, submission(occurred_at=sunday), after_midnight),
        envelope(4, completion(occurred_at=monday), after_midnight),
    ]
    history = LearningHistory.replay_envelopes(ITEMS, reversed(events))
    report = analyze_user(history, "u1", as_of=after_midnight)
    before_application = analyze_user(history, "u1", as_of=monday)
    before_late_event = analyze_user(history, "u1", as_of=after_midnight, through_sequence=2)

    assert report["weekly"]["week_start"] == "2026-01-05"
    assert report["weekly"]["days"][0] == {"date": "2026-01-05", "first_attempts": 1, "completed_sessions": 1}
    assert report["summary"]["first_attempts"] == 2
    assert [point["sequence"] for point in report["skills"]["fact"]["theta_history"]] == ["2", "3"]
    assert report["skills"]["fact"]["previous_theta"] == 0.0
    assert before_application["summary"]["first_attempts"] == before_late_event["summary"]["first_attempts"] == 1
    assert before_application["skills"] == before_late_event["skills"]
    assert before_late_event["through_sequence"] == "2"
    sunday_report = analyze_user(history, "u1", as_of=sunday)
    assert sunday_report["summary"]["first_attempts"] == 0
