import json

import pytest

from neuroknot_ml.elo import EloModel
from neuroknot_ml.selection import PassageCandidate, register_passage, select_passage

SKILLS = ("fact", "inference", "vocab")


def generated(passage_id, **quiz_fields):
    return {
        "passage_id": passage_id,
        "quiz": {"questions": [{"skill": skill} for skill in SKILLS], **quiz_fields},
    }


def candidate(passage_id, **quiz_fields):
    return PassageCandidate.from_generated(
        generated(passage_id, **quiz_fields), [f"{passage_id}:{i}" for i in range(3)],
    )


def test_neutral_registration_cannot_distinguish_passage_hints():
    model = EloModel()
    easy = candidate("easy", difficulty_hint=1)
    hard = candidate("hard", difficulty_hint=5)
    for passage in (easy, hard):
        for question in passage.questions:
            model.register_item(question.item_id, question.skill)

    easy_scores = select_passage(model, "new", [easy]).scores
    hard_scores = select_passage(model, "new", [hard]).scores
    assert easy_scores == hard_scores
    assert easy_scores.probabilities == (0.5, 0.5, 0.5)


def test_hints_change_selection_for_new_and_experienced_learners():
    model = EloModel()
    easy = candidate("easy", difficulty_hint=1)
    hard = candidate("hard", difficulty_hint=5)
    register_passage(model, easy)
    register_passage(model, hard)

    model.register_user("experienced", "autonomous")
    for skill in SKILLS:
        model.register_item(f"practice:{skill}", skill)
        for _ in range(4):
            model.update("experienced", f"practice:{skill}", True)

    for user, history, expected in (
        ("new", {}, easy),
        ("experienced", dict.fromkeys(SKILLS, 4), hard),
    ):
        selection = select_passage(model, user, [hard, easy], skill_attempts=history)
        assert selection.passage == expected
        assert selection.scores.probabilities == tuple(model.predict(user, q.item_id) for q in expected.questions)
        assert selection == select_passage(model, user, [easy, hard], skill_attempts=history)


@pytest.mark.parametrize(("hint", "prior"), [(1, -1.6), (2, -0.8), (3, 0.0), (4, 0.8), (5, 1.6)])
def test_hints_reuse_existing_elo_star_mapping(hint, prior):
    model = EloModel()
    passage = candidate("passage", difficulty_hint=hint)
    register_passage(model, passage)

    assert [model.item_difficulty(q.item_id) for q in passage.questions] == [prior] * 3


@pytest.mark.parametrize("quiz_fields", [{}, {"difficulty_hint": None}])
def test_missing_or_null_hint_keeps_neutral_prior(quiz_fields):
    model = EloModel()
    passage = candidate("passage", **quiz_fields)
    register_passage(model, passage)

    assert passage.difficulty_hint is None
    assert [model.item_difficulty(q.item_id) for q in passage.questions] == [0.0] * 3


def test_explicit_difficulties_override_hint_and_custom_mapping_is_used():
    model = EloModel(star_prior={1: -2.0, 5: 2.5})
    passage = candidate("passage", difficulty_hint=5)
    first, second, third = (q.item_id for q in passage.questions)
    register_passage(model, passage, item_difficulties={first: 1, second: None})

    assert [model.item_difficulty(i) for i in (first, second, third)] == [-2.0, 2.5, 2.5]


@pytest.mark.parametrize("invalid", [0, 6, True, 2.5, "3", float("nan")])
def test_invalid_hint_and_override_are_rejected_before_registration(invalid):
    with pytest.raises(ValueError, match="difficulty_hint"):
        candidate("passage", difficulty_hint=invalid)

    model = EloModel()
    passage = candidate("passage", difficulty_hint=3)
    with pytest.raises(ValueError, match="item_difficulties"):
        register_passage(model, passage, item_difficulties={passage.questions[-1].item_id: invalid})
    assert model.to_state()["items"] == {}


@pytest.mark.parametrize("ids", [["q1", "q2"], ["q1", "q1", "q3"], ["q1", " ", "q3"], "abc", [1, 2, 3]])
def test_generated_quiz_requires_three_distinct_nonempty_string_ids(ids):
    with pytest.raises(ValueError):
        PassageCandidate.from_generated(generated("passage", difficulty_hint=3), ids)


def test_unknown_override_id_and_existing_skill_mismatch_do_not_partially_register():
    model = EloModel()
    passage = candidate("passage", difficulty_hint=3)
    last = passage.questions[-1].item_id
    model.register_item(last, "main_idea", 1)
    before = model.to_state()

    with pytest.raises(ValueError, match="unknown item ID"):
        register_passage(model, passage, item_difficulties={"typo": 5})
    with pytest.raises(ValueError, match="already registered for skill"):
        register_passage(model, passage)
    assert model.to_state() == before


def test_reregistration_after_json_restore_preserves_learned_difficulty_and_selection():
    model = EloModel()
    first = candidate("first", difficulty_hint=1)
    second = candidate("second", difficulty_hint=5)
    register_passage(model, first)
    register_passage(model, second)
    model.update("u1", first.questions[0].item_id, False)
    restored = EloModel.from_state(json.loads(json.dumps(model.to_state(), allow_nan=False)))

    register_passage(restored, candidate("first", difficulty_hint=4))

    assert restored.to_state() == model.to_state()
    assert select_passage(restored, "u1", [second, first]) == select_passage(model, "u1", [first, second])
