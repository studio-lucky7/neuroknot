"""develop의 공개 API만 사용해 통합 시 보존해야 할 동작을 검증한다."""

import json
from copy import deepcopy

import pytest

from neuroknot_ml.elo import EloModel
from neuroknot_ml.learning_events import EventValidationError
from neuroknot_ml.learning_history import CatalogItem, EventConflictError, LearningHistory
from test_learning_events import completion, exposure, submission

ITEMS = (CatalogItem("q1", "v1", "fact"),)
AT = "2026-01-05T00:00:00Z"


def shared_item_events():
    return [
        exposure(item_ids=["q1"], occurred_at=AT),
        exposure(event_id="e-other", exposure_id="x2", user_id="u2", item_ids=["q1"], occurred_at=AT),
        submission(occurred_at=AT),
        submission(event_id="a-other", exposure_id="x2", user_id="u2", submission_id="s2",
                   is_correct=False, occurred_at=AT),
    ]


def test_simultaneous_shared_item_answers_depend_on_input_order():
    first, second, correct, incorrect = shared_item_events()
    chronological = LearningHistory.replay(ITEMS, [first, second, correct, incorrect])
    reversed_answers = LearningHistory.replay(ITEMS, [first, second, incorrect, correct])

    for history in (chronological, reversed_answers):
        before, after = (record.attempt for record in history.records[-2:])
        assert before.probability == 0.5
        assert after.difficulty_before == before.difficulty_after
    assert chronological.records[-1].attempt.probability > 0.5
    assert reversed_answers.records[-1].attempt.probability < 0.5
    assert chronological.item_difficulty("q1") < 0 < reversed_answers.item_difficulty("q1")


def test_source_order_preserves_shared_item_replay_with_shuffled_delivery():
    events = shared_item_events()
    online = LearningHistory(ITEMS)
    for event in events:
        online.apply(event)

    # 모의 서버 순번은 이벤트 외부에 보관한다. 현재 V1 스키마에는 순번 필드가 없다.
    positions = list(enumerate(events, start=1))
    shuffled_delivery = [positions[i] for i in (3, 1, 2, 0)]
    ordered_payloads = [event for _, event in sorted(shuffled_delivery)]
    rebuilt = LearningHistory.replay(ITEMS, ordered_payloads)

    assert rebuilt.records == online.records
    assert rebuilt.item_difficulty("q1") == online.item_difficulty("q1")
    assert rebuilt.user_rating("u1", "fact") == online.user_rating("u1", "fact")
    assert rebuilt.user_rating("u2", "fact") == online.user_rating("u2", "fact")


def test_restart_restores_old_submission_receipts_even_after_later_updates():
    first, second, answer, later_answer = shared_item_events()
    history = LearningHistory(ITEMS)
    history.apply(first)
    original = history.apply(answer)
    alias = {**answer, "event_id": "answer-alias"}
    history.apply(alias)
    history.apply(completion(occurred_at=AT))
    history.apply(second)
    history.apply({**later_answer, "occurred_at": "2026-01-05T00:01:00Z"})

    restored = LearningHistory.replay(ITEMS, json.loads(json.dumps(history.event_log(), allow_nan=False)))
    before = restored.item_difficulty("q1")
    assert restored.apply(answer) == restored.apply(alias) == original
    assert restored.apply({**answer, "event_id": "another-alias"}) == original
    with pytest.raises(EventConflictError, match="event_id"):
        restored.apply({**alias, "is_correct": False})
    with pytest.raises(EventConflictError, match="submission"):
        restored.apply({**answer, "event_id": "conflict", "is_correct": False})
    assert restored.records == history.records
    assert restored.item_difficulty("q1") == before

    # 최초 응답 인덱스는 영수증뿐 아니라 신규 노출의 재시도 분류에도 필요하다.
    restored.apply(exposure(event_id="new-exposure", exposure_id="x3", item_ids=["q1"],
                            occurred_at="2026-01-05T00:02:00Z"))
    retry = {**answer, "event_id": "retry", "submission_id": "retry", "exposure_id": "x3",
             "occurred_at": "2026-01-05T00:03:00Z"}
    with pytest.raises(EventValidationError, match="is_retry"):
        restored.apply(retry)
    assert not restored.apply({**retry, "is_retry": True}).attempt.elo_updated
    assert restored.item_difficulty("q1") == before


def test_applying_the_checkpoint_prefix_again_changes_an_already_updated_model():
    model = EloModel()
    model.register_item("q1", "fact")
    model.update("u1", "q1", True)
    # 현재 develop에서는 메모리 복제로 이미 갱신된 체크포인트를 모의한다.
    restored = deepcopy(model)
    assert restored.predict("u1", "q1") == model.predict("u1", "q1")

    restored.update("u1", "q1", True)

    assert restored.user_rating("u1", "fact") > model.user_rating("u1", "fact")
    assert restored.item_difficulty("q1") < model.item_difficulty("q1")


def test_reregistering_same_item_preserves_learned_difficulty_and_update_count():
    model = EloModel()
    model.register_item("q1", "fact", 1)
    model.update("u1", "q1", True)
    reference = deepcopy(model)

    model.register_item("q1", "fact", 5)

    assert model.item_difficulty("q1") == reference.item_difficulty("q1")
    assert model.update("u2", "q1", False) == reference.update("u2", "q1", False)
    assert model.item_difficulty("q1") == reference.item_difficulty("q1")


def test_catalog_rejects_reusing_an_item_id_for_a_different_version():
    with pytest.raises(EventValidationError, match="duplicate catalog item ID"):
        LearningHistory([*ITEMS, CatalogItem("q1", "v2", "fact", 5)])

    second_version = CatalogItem("q1-v2", "v2", "fact", 5)
    history = LearningHistory.replay(
        [*ITEMS, second_version], [exposure(item_ids=["q1"], occurred_at=AT), submission(occurred_at=AT)],
    )
    assert history.item_difficulty("q1") == -0.2
    assert history.item_difficulty("q1-v2") == 1.6
