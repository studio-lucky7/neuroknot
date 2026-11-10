import json

import pytest

from neuroknot_ml.elo import EloModel
from neuroknot_ml.learning_analytics import analyze_user
from neuroknot_ml.learning_events import EventValidationError
from neuroknot_ml.learning_history import EventConflictError, LearningHistory
from test_integrated_selection import register_quiz
from test_learning_events import completion, exposure, submission
from test_sequenced_learning import AT


def round_trip(value):
    return json.loads(json.dumps(value, allow_nan=False))


def prepared_history():
    history = LearningHistory([], onboarding_levels={"u1": "cruising"}, stream_id="test-stream")
    quiz = register_quiz(history, "p1", 5, item_difficulties={"p1-q0": 2})
    ids = [q.item_id for q in quiz.questions]
    history.accept_event(exposure(item_ids=ids, occurred_at=AT), applied_at=AT)
    answer = submission(item_id=ids[0], occurred_at=AT)
    original = history.accept_event(answer, applied_at=AT)
    alias = {**answer, "event_id": "alias"}
    assert history.accept_event(alias, applied_at=AT) == original
    return history, quiz, ids, answer, alias, original


def test_real_snapshot_resume_matches_full_replay_without_updating_prefix(monkeypatch):
    history, quiz, ids, _, _, _ = prepared_history()
    checkpoint = round_trip(history.checkpoint())
    assert checkpoint["through_sequence"] == "3"
    assert checkpoint["model"]["items"][ids[0]]["attempts"] == 1

    with monkeypatch.context() as patch:
        def reject_prefix_update(*args, **kwargs):
            pytest.fail("Elo update during checkpoint restore")

        patch.setattr(EloModel, "update", reject_prefix_update)
        restored = LearningHistory.from_checkpoint(checkpoint, expected_stream_id="test-stream")
    assert restored.checkpoint() == checkpoint
    assert restored.predict("u1", ids[0]) == history.predict("u1", ids[0])
    assert restored.predict("u2", ids[0]) == history.predict("u2", ids[0])

    new_quiz = register_quiz(history, "p2", 1)
    register_quiz(restored, "p2", 1)
    register_quiz(restored, "p1", 1)
    learned = history.item_difficulty(ids[0])
    assert restored.item_difficulty(ids[0]) == learned
    assert [item.difficulty for item in restored.catalog if item.item_id in ids] == [2, 5, 5]
    for event in [
        exposure(user_id="u2", exposure_id="x2", event_id="u2-ex", item_ids=ids, occurred_at=AT),
        submission(user_id="u2", exposure_id="x2", item_id=ids[0], event_id="u2-answer",
                   submission_id="u2-answer", occurred_at=AT, is_correct=False),
        submission(item_id=ids[1], skill="inference", event_id="infer", submission_id="infer", occurred_at=AT),
        submission(item_id=ids[2], skill="vocab", event_id="vocab", submission_id="vocab", occurred_at=AT),
        completion(occurred_at=AT),
    ]:
        history.accept_event(event, applied_at=AT)
    restored.replay_suffix(reversed(history.event_log()[3:]))
    full = LearningHistory.replay_envelopes(
        history.catalog, reversed(history.event_log()), quiz_catalog=history.quiz_catalog,
        onboarding_levels={"u1": "cruising"}, stream_id="test-stream",
    )
    assert restored.checkpoint() == full.checkpoint() == history.checkpoint()
    assert restored.records == full.records
    for user in ("u1", "u2"):
        for item_id in ids:
            assert restored.predict(user, item_id) == full.predict(user, item_id)
        assert restored.recommend(user, [quiz, new_quiz]) == full.recommend(user, [quiz, new_quiz])
        assert analyze_user(restored, user, as_of=AT) == analyze_user(full, user, as_of=AT)


def test_lost_response_and_old_alias_are_idempotent_after_checkpoint():
    history, _, ids, answer, alias, original = prepared_history()
    restored = LearningHistory.from_checkpoint(round_trip(history.checkpoint()))
    old_envelope = history.event_log()[1]
    later = "2026-01-05T01:00:00Z"
    assert restored.accept_event(answer, applied_at=later) == original
    assert restored.accept_event(alias, applied_at=later) == original
    assert restored.apply_envelope(old_envelope) == original
    assert restored.checkpoint() == history.checkpoint()
    assert restored.accept_event({**answer, "event_id": "late-alias"}, applied_at=later) == original
    with pytest.raises(EventConflictError, match="event_id"):
        restored.accept_event({**alias, "is_correct": False}, applied_at=later)
    with pytest.raises(EventConflictError, match="submission"):
        restored.accept_event({**answer, "event_id": "conflict", "is_correct": False}, applied_at=later)
    assert restored.checkpoint()["through_sequence"] == "4"
    assert restored.checkpoint()["model"]["items"][ids[0]]["attempts"] == 1
    assert analyze_user(restored, "u1", as_of=later)["summary"]["first_attempts"] == 1


def test_checkpoint_rejects_missing_cursor_metadata_and_inconsistent_model():
    history, _, ids, _, _, _ = prepared_history()
    state = history.checkpoint()
    with pytest.raises(EventValidationError, match="through_sequence"):
        LearningHistory.from_checkpoint({**state, "through_sequence": "2"})
    with pytest.raises(EventValidationError, match="revision"):
        LearningHistory.from_checkpoint({**state, "onboarding_levels": {"u1": "autonomous"}})
    with pytest.raises(EventValidationError, match="stream_id"):
        LearningHistory.from_checkpoint(state, expected_stream_id="wrong-stream")
    corrupt = round_trip(state)
    corrupt["model"]["items"][ids[0]]["attempts"] += 1
    with pytest.raises(EventValidationError, match="journal boundary"):
        LearningHistory.from_checkpoint(corrupt)
    corrupt = round_trip(state)
    corrupt["journal"][-1]["attempt"]["probability"] = 0.0
    with pytest.raises(EventValidationError, match="alias"):
        LearningHistory.from_checkpoint(corrupt)
