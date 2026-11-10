import pytest

import neuroknot_ml.learning_history as history_module
from neuroknot_ml.learning_events import EventValidationError
from neuroknot_ml.learning_history import LearningHistory
from neuroknot_ml.selection import SelectionConfig
from test_learning_events import exposure, submission
from test_sequenced_learning import AT


def register_quiz(history, passage, hint, *, item_version="v1", item_difficulties=None):
    ids = [f"{passage}-q{i}" for i in range(3)]
    generated = {
        "passage_id": passage,
        "quiz": {"difficulty_hint": hint, "questions": [{"skill": s} for s in ("fact", "inference", "vocab")]},
    }
    return history.register_generated(
        generated, ids, quiz_version="quiz-v1", item_versions=dict.fromkeys(ids, item_version),
        item_difficulties=item_difficulties,
    )


def test_core_recommendation_uses_analytics_ratings_exposures_and_first_answer_counts():
    history = LearningHistory([])
    easy = register_quiz(history, "easy", 1)
    hard = register_quiz(history, "hard", 5)
    config = SelectionConfig(cold_start_attempts=2)
    initial = history.recommend("u1", [hard, easy], config=config)
    assert initial.through_sequence == 0
    assert initial.selection.passage == easy
    ids = [q.item_id for q in easy.questions]
    history.accept_event(exposure(passage_id="easy", item_ids=ids, occurred_at=AT), applied_at=AT)
    first = submission(passage_id="easy", item_id=ids[0], occurred_at=AT)
    old_prediction = history.predict("u2", ids[0])
    history.accept_event(first, applied_at=AT)
    history.accept_event({**first, "event_id": "retry", "submission_id": "retry", "is_retry": True}, applied_at=AT)
    assert history.predict("u2", ids[0]) > old_prediction
    recommendation = history.recommend("u1", [easy, hard], config=config)

    assert recommendation.through_sequence == 3
    assert recommendation.selection.passage == hard
    assert recommendation.selection.excluded_seen == 1
    assert recommendation.selection.scores.target_p == 0.8
    history.accept_event(submission(
        passage_id="easy", item_id=ids[1], skill="inference", event_id="s-infer", submission_id="s-infer",
        occurred_at=AT,
    ), applied_at=AT)
    assert history.recommend("u1", [hard, easy], config=config).selection.scores.target_p == 0.7


def test_generated_initialization_and_reregistration_use_one_catalog_without_overwriting_b():
    history = LearningHistory([])
    candidate = register_quiz(history, "p1", 5, item_difficulties={"p1-q0": 1})
    ids = [q.item_id for q in candidate.questions]
    assert [item.difficulty for item in history.catalog] == [1, 5, 5]
    assert [history.item_difficulty(item_id) for item_id in ids] == [-1.6, 1.6, 1.6]
    with pytest.raises(EventValidationError, match="quiz version"):
        history.accept_event(exposure(item_ids=ids, quiz_version="wrong", occurred_at=AT), applied_at=AT)
    history.accept_event(exposure(item_ids=ids, occurred_at=AT), applied_at=AT)
    history.accept_event(submission(item_id=ids[0], occurred_at=AT), applied_at=AT)
    learned = history.item_difficulty(ids[0])
    register_quiz(history, "p1", 2)

    assert history.item_difficulty(ids[0]) == learned
    assert [item.difficulty for item in history.catalog] == [1, 5, 5]
    with pytest.raises(EventValidationError, match="another version"):
        register_quiz(history, "p1", 2, item_version="v2")
    replayed = LearningHistory.replay_envelopes(history.catalog, history.event_log(), quiz_catalog=history.quiz_catalog)
    assert replayed.records == history.records
    assert replayed.item_difficulty(ids[0]) == learned


def test_selection_sees_one_cursor_and_cannot_mutate_elo(monkeypatch):
    history = LearningHistory([])
    candidate = register_quiz(history, "p1", 1)
    ids = [q.item_id for q in candidate.questions]
    initial_p = history.predict("u2", ids[0])
    original_select = history_module.select_passage

    def apply_while_scoring(view, user_id, candidates, **options):
        assert not hasattr(view, "update") and not hasattr(view, "register_item")
        with pytest.raises(TypeError):
            view.probabilities[ids[0]] = 0.0
        history.accept_event(exposure(user_id="u2", item_ids=ids, occurred_at=AT), applied_at=AT)
        history.accept_event(submission(user_id="u2", item_id=ids[0], occurred_at=AT), applied_at=AT)
        return original_select(view, user_id, candidates, **options)

    with monkeypatch.context() as patch:
        patch.setattr(history_module, "select_passage", apply_while_scoring)
        selected = history.recommend("u2", [candidate])
    assert selected.through_sequence == 0
    assert selected.selection.scores.probabilities[0] == initial_p
    assert history.predict("u2", ids[0]) != initial_p
    events = history.event_log()
    exhausted = history.recommend("u2", [candidate])
    assert exhausted.through_sequence == 2 and exhausted.selection.passage is None
    assert history.event_log() == events
