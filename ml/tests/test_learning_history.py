import json

import pytest

from neuroknot_ml.elo import EloModel
from neuroknot_ml.learning_events import EventValidationError
from neuroknot_ml.learning_history import CatalogItem, EventConflictError, LearningHistory
from test_learning_events import completion, exposure, submission

ITEMS = (CatalogItem("q1", "v1", "fact"), CatalogItem("q2", "v1", "vocab", 4))


def test_first_answer_traces_elo_and_duplicates_return_original_result():
    history = LearningHistory(ITEMS)
    history.apply(exposure())
    event = submission()
    record = history.apply(event)
    trace = record.attempt
    assert trace.elo_updated
    assert (trace.probability, trace.theta_before, trace.difficulty_before) == (0.5, 0.0, 0.0)
    assert (trace.theta_after, trace.difficulty_after) == (0.4, -0.2)
    assert history.apply(event) is record
    alias = {**event, "event_id": "alias", "occurred_at": "2026-01-04T15:01:00Z"}
    assert history.apply(alias) is record
    assert len(history.records) == 2
    assert len(history.event_log()) == 3

    replayed = LearningHistory.replay(ITEMS, json.loads(json.dumps(history.event_log(), allow_nan=False)))
    assert replayed.records == history.records
    assert replayed.event_log() == history.event_log()
    with pytest.raises(EventConflictError, match="event_id"):
        replayed.apply({**alias, "is_correct": False})


@pytest.mark.parametrize("event_id", ["e2", "new-event"])
def test_conflicting_event_or_submission_id_leaves_state_unchanged(event_id):
    history = LearningHistory.replay(ITEMS, [exposure(), submission()])

    with pytest.raises(EventConflictError):
        history.apply(submission(event_id=event_id, is_correct=False))
    assert len(history.records) == 2
    assert history.item_difficulty("q1") == -0.2


def test_two_retries_and_reexposure_leave_elo_unchanged():
    history = LearningHistory.replay(ITEMS, [exposure(), submission(is_correct=False)])
    for i in (2, 3):
        record = history.apply(submission(
            event_id=f"retry-{i}", submission_id=f"s{i}", is_retry=True, occurred_at=f"2026-01-05T00:0{i}:00+09:00",
        ))
        assert not record.attempt.elo_updated
        assert record.attempt.theta_after == record.attempt.theta_before == -0.4
        assert record.attempt.difficulty_after == record.attempt.difficulty_before == 0.2
    history.apply(exposure(event_id="next", exposure_id="x2", occurred_at="2026-01-05T00:04:00+09:00"))
    next_answer = submission(
        event_id="next-answer", exposure_id="x2", submission_id="next-sub", occurred_at="2026-01-05T00:05:00+09:00",
    )
    with pytest.raises(EventValidationError, match="is_retry"):
        history.apply(next_answer)
    assert not history.apply({**next_answer, "is_retry": True}).attempt.elo_updated


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"user_id": "u2"}, "user"), ({"passage_id": "other"}, "passage"), ({"item_id": "other"}, "item"),
        ({"item_version": "v2"}, "version"), ({"skill": "inference"}, "skill"), ({"is_retry": True}, "is_retry"),
    ],
)
def test_invalid_answers_do_not_change_history_or_elo(change, error):
    history = LearningHistory.replay(ITEMS, [exposure()])

    with pytest.raises(EventValidationError, match=error):
        history.apply(submission(**change))
    assert len(history.records) == 1
    assert history.item_difficulty("q1") == 0.0
    assert history.user_rating("u1", "fact") == 0.0


def test_missing_exposure_unknown_item_and_submission_before_exposure():
    history = LearningHistory(ITEMS)
    with pytest.raises(EventValidationError, match="unknown exposure"):
        history.apply(submission())
    with pytest.raises(EventValidationError, match="unknown exposed item"):
        history.apply(exposure(item_ids=["bad"]))
    early = submission(occurred_at="2026-01-04T23:59:00+09:00")
    with pytest.raises(EventValidationError, match="unknown exposure"):
        LearningHistory.replay(ITEMS, [exposure(), early])
    assert history.records == ()


def test_completion_requires_all_answers_and_duplicate_is_idempotent():
    history = LearningHistory.replay(ITEMS, [exposure(), submission(is_correct=False)])
    with pytest.raises(EventValidationError, match="every exposed item"):
        history.apply(completion())
    history.apply(submission(
        event_id="vocab", submission_id="s2", item_id="q2", skill="vocab", is_correct=False,
    ))
    record = history.apply(completion())
    assert history.apply(completion()) is record
    assert history.apply(completion(event_id="completed-alias")) is record
    with pytest.raises(EventConflictError, match="completion"):
        history.apply(completion(event_id="conflict", status="abandoned"))
    with pytest.raises(EventValidationError, match="ended"):
        history.apply(submission(
            event_id="late", submission_id="late", is_retry=True, occurred_at="2026-01-05T00:03:00+09:00",
        ))
    assert len(history.records) == 4


def test_exposure_alias_and_abandonment_without_answer():
    history = LearningHistory(ITEMS)
    first = history.apply(exposure())
    assert history.apply(exposure(event_id="other")) is first
    with pytest.raises(EventConflictError, match="exposure"):
        history.apply(exposure(event_id="conflict", quiz_version="v2"))
    assert history.apply(completion(status="abandoned")).attempt is None
    assert history.user_rating("u1", "fact") == 0.0


def test_replay_reorders_timestamps_and_preserves_global_shared_item_updates():
    u2_exposure = exposure(event_id="u2-exposure", user_id="u2", exposure_id="x2")
    u2_answer = submission(
        event_id="u2-answer", submission_id="s2", user_id="u2", exposure_id="x2", is_correct=False,
        occurred_at="2026-01-05T00:02:00+09:00",
    )
    events = [exposure(), u2_exposure, submission(), u2_answer]
    levels = {"u1": "cruising", "u2": "autonomous"}
    online = LearningHistory(ITEMS, onboarding_levels=levels)
    for event in events:
        online.apply(event)
    replayed = LearningHistory.replay(ITEMS, [u2_answer, *events[:3]], onboarding_levels=levels)

    reference = EloModel()
    reference.register_item("q1", "fact")
    for user_id, level in levels.items():
        reference.register_user(user_id, level)
    assert reference.update("u1", "q1", True) == replayed.records[2].attempt.probability
    assert reference.predict("u2", "q1") == replayed.records[3].attempt.probability
    reference.update("u2", "q1", False)
    assert online.records == replayed.records
    assert replayed.item_difficulty("q1") == reference.item_difficulty("q1")
    assert replayed.user_rating("u1", "fact") == reference.user_rating("u1", "fact")
    assert replayed.user_rating("u2", "fact") == reference.user_rating("u2", "fact")

    prefix = LearningHistory.replay(ITEMS, events[:3], onboarding_levels=levels)
    assert prefix.records == replayed.records[:3]
    with pytest.raises(EventValidationError, match="chronological"):
        online.apply(exposure(event_id="old", exposure_id="old"))


def test_equal_timestamp_replay_respects_source_order():
    answer = submission(occurred_at=exposure()["occurred_at"])
    assert LearningHistory.replay(ITEMS, [exposure(), answer]).records[-1].attempt.elo_updated
    with pytest.raises(EventValidationError, match="unknown exposure"):
        LearningHistory.replay(ITEMS, [answer, exposure()])
