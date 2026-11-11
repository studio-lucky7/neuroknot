import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest
from neuroknot_gen.schemas import GeneratedQuiz, Passage
from neuroknot_gen.validate import check_quiz

from neuroknot_ml.learning_events import EventValidationError
from neuroknot_ml.learning_history import EventConflictError
from neuroknot_ml.service_workflow import PredictionService
from scripts.run_service_workflow import MONDAY, SUNDAY, load_fixtures, run_demo

CLOCK = {"occurred_at": SUNDAY, "applied_at": SUNDAY}
LATER = {"occurred_at": MONDAY, "applied_at": MONDAY}


@pytest.mark.parametrize("fixture", load_fixtures(), ids=lambda fixture: fixture["passage"]["id"])
def test_workflow_fixtures_pass_real_generation_validation(fixture):
    passage = Passage.model_validate(fixture["passage"])
    generated = GeneratedQuiz.model_validate(fixture["generated"])

    assert generated.passage_id == passage.id
    assert check_quiz(generated.quiz, passage) == []


def register(service, fixture, *, version="v1", item_difficulties=None):
    return service.register_quiz(
        fixture["generated"], quiz_version=version, passage_body=fixture["passage"]["body"],
        item_difficulties=item_difficulties,
    )


def confirm(service, quiz, *, user="u1", exposure="x1", clock=CLOCK):
    return service.confirm_exposure(
        user, exposure_id=exposure, passage_id=quiz["passage_id"], quiz_version=quiz["quiz_version"], **clock,
    )


def answer(quiz, slot, submission_id, choice, *, exposure="x1", clock=CLOCK):
    return {
        "exposure_id": exposure, "item_id": quiz["questions"][slot]["item_id"], "submission_id": submission_id,
        "choice_index": choice, **clock,
    }


def test_recommendation_is_read_only_and_confirmation_is_idempotent():
    service = PredictionService()
    for fixture in load_fixtures():
        register(service, fixture)
    before = service.checkpoint()
    first, stale = service.recommend("u1"), service.recommend("u1")

    assert first == stale
    assert first["through_sequence"] == "0"
    assert service.checkpoint() == before
    quiz = first["quiz"]
    assert set(quiz) == {"passage_id", "quiz_version", "passage_body", "questions"}
    assert all(set(question) == {"item_id", "stem", "options"} for question in quiz["questions"])
    exposed = confirm(service, quiz)
    assert exposed["quiz"] == quiz
    assert confirm(service, stale["quiz"], clock=LATER) == exposed
    with pytest.raises(EventConflictError, match="already been exposed"):
        confirm(service, stale["quiz"], exposure="x2", clock=LATER)
    assert service.recommend("u1")["quiz"]["passage_id"] != quiz["passage_id"]
    assert service.analyze("u1", as_of=SUNDAY)["summary"]["exposures"] == 1
    assert service.checkpoint()["history"]["through_sequence"] == "1"


def test_server_grades_mixed_answers_and_only_first_valid_attempt_updates_elo():
    service = PredictionService()
    first_fixture, second_fixture = load_fixtures()
    quiz, other_quiz = register(service, first_fixture), register(service, second_fixture)
    with pytest.raises(ValueError, match="unknown exposure"):
        service.submit_answer("u1", **answer(quiz, 0, "s1", 0))
    confirm(service, quiz)
    with pytest.raises(ValueError, match="unknown exposure"):
        service.submit_answer("other-user", **answer(quiz, 0, "s1", 0))
    with pytest.raises(ValueError, match="not exposed"):
        service.submit_answer("u1", **answer(other_quiz, 0, "s1", 0))
    with pytest.raises(EventValidationError, match="every exposed item"):
        service.complete_learning("u1", exposure_id="x1", **CLOCK)
    first = answer(quiz, 0, "s1", 0)
    with pytest.raises(TypeError):
        service.submit_answer("u1", **first, is_correct=True, is_retry=False)
    with pytest.raises(ValueError, match="choice index"):
        service.submit_answer("u1", **{**first, "choice_index": True})
    result = service.submit_answer("u1", **first)
    assert result == {"submission_id": "s1", "is_correct": False, "is_retry": False, "sequence": "2"}
    assert service.submit_answer("u1", **{**first, **LATER}) == result
    with pytest.raises(EventConflictError, match="different answer"):
        service.submit_answer("u1", **{**first, "choice_index": 2})  # both choices are wrong
    retry = service.submit_answer("u1", **answer(quiz, 0, "s-retry", 1))
    assert retry["is_correct"] and retry["is_retry"]
    service.submit_answer("u1", **answer(quiz, 1, "s2", 2))
    service.submit_answer("u1", **answer(quiz, 2, "s3", 0))
    done = service.complete_learning("u1", exposure_id="x1", **CLOCK)
    assert service.complete_learning("u1", exposure_id="x1", **LATER) == done
    with pytest.raises(EventValidationError, match="already ended"):
        service.submit_answer("u1", **answer(quiz, 0, "late", 1))

    model = service.checkpoint()["history"]["model"]
    assert model["items"][first["item_id"]]["attempts"] == 1
    assert model["user_skills"]["u1"]["fact"]["attempts"] == 1
    report = service.analyze("u1", as_of=SUNDAY)
    assert report["summary"]["first_attempts"] == 3
    assert report["summary"]["correct_first_attempts"] == 2
    assert report["summary"]["retries"] == 1
    assert report["summary"]["completed_sessions"] == 1
    assert report["skills"]["fact"]["theta_change"] < 0


def test_shared_item_keeps_one_difficulty_across_users():
    service = PredictionService()
    quiz = register(service, load_fixtures()[0])
    confirm(service, quiz)
    confirm(service, quiz, user="u2", exposure="x2")
    first = answer(quiz, 0, "s1", 0)
    service.submit_answer("u1", **first)
    before = service.checkpoint()["history"]["model"]["items"][first["item_id"]]
    second = service.submit_answer("u2", **answer(quiz, 0, "s2", 1, exposure="x2"))
    history = service.checkpoint()["history"]

    assert not second["is_retry"]
    assert history["journal"][-1]["attempt"]["difficulty_before"] == before["difficulty"]
    assert history["model"]["items"][first["item_id"]]["attempts"] == 2


@pytest.mark.parametrize("restore", [False, True], ids=["live", "restored"])
def test_versions_keep_ids_stable_and_old_exposure_keeps_original_grading(restore):
    service = PredictionService()
    fixture = load_fixtures()[0]
    first = register(service, fixture, item_difficulties={0: 3})
    confirm(service, first)
    assert register(service, fixture, item_difficulties={0: 3}) == first
    changed = deepcopy(fixture)
    question = changed["generated"]["quiz"]["questions"][0]
    question["options"][0], question["options"][1] = question["options"][1], question["options"][0]
    question["answer_index"] = 0
    question["distractors"][0]["option_index"] = 1
    assert check_quiz(GeneratedQuiz.model_validate(changed["generated"]).quiz,
                      Passage.model_validate(changed["passage"])) == []
    with pytest.raises(EventConflictError, match="quiz_version"):
        register(service, changed, item_difficulties={0: 3})
    second = register(service, changed, version="v2")
    assert {q["item_id"] for q in first["questions"]}.isdisjoint(q["item_id"] for q in second["questions"])
    if restore:
        service = PredictionService.from_checkpoint(json.loads(json.dumps(service.checkpoint(), allow_nan=False)))
    assert service.recommend("u2")["quiz"] == second
    with pytest.raises(ValueError, match="not active"):
        confirm(service, first, user="u2", exposure="x2")
    assert service.submit_answer("u1", **answer(first, 0, "s1", 1))["is_correct"]
    before_reregistration = service.checkpoint()
    if restore:
        service = PredictionService.from_checkpoint(json.loads(json.dumps(before_reregistration, allow_nan=False)))
        assert service.checkpoint() == before_reregistration
    learned = before_reregistration["history"]["model"]["items"][first["questions"][0]["item_id"]]
    assert learned["attempts"] == 1 and learned["difficulty"] != 0.0
    assert register(service, fixture, item_difficulties={0: 3}) == first
    assert service.checkpoint() == before_reregistration
    with pytest.raises(EventConflictError, match="quiz_version"):
        register(service, changed, item_difficulties={0: 3})
    assert service.checkpoint() == before_reregistration
    assert service.recommend("u2")["quiz"] == second


def test_competing_confirmations_are_serialized_in_one_service():
    service = PredictionService()
    register(service, load_fixtures()[0])
    barrier = Barrier(2, timeout=5)

    def attempt(exposure_id):
        quiz = service.recommend("u1")["quiz"]
        barrier.wait()
        try:
            return confirm(service, quiz, exposure=exposure_id)
        except EventConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["x1", "x2"]))

    assert sum(result is not None for result in results) == 1
    assert service.checkpoint()["history"]["through_sequence"] == "1"


def test_checkpoint_restores_grading_receipt_and_rejects_wrong_choice_collision():
    service = PredictionService()
    quiz = register(service, load_fixtures()[0])
    confirm(service, quiz)
    original = answer(quiz, 0, "s1", 0)
    result = service.submit_answer("u1", **original)
    snapshot = json.loads(json.dumps(service.checkpoint(), allow_nan=False))
    restored = PredictionService.from_checkpoint(snapshot)

    assert restored.submit_answer("u1", **{**original, **LATER}) == result
    with pytest.raises(EventConflictError, match="different answer"):
        restored.submit_answer("u1", **{**original, "choice_index": 2, **LATER})
    assert restored.checkpoint() == snapshot
    assert restored.analyze("u1", as_of=MONDAY) == service.analyze("u1", as_of=MONDAY)
    with pytest.raises(ValueError, match="receipts"):
        PredictionService.from_checkpoint({**snapshot, "choices": {}})


def test_demo_replays_full_workflow_with_seoul_week_boundary():
    result = run_demo()

    assert result["data"] == "synthetic_test_fixtures"
    assert result["matches_uninterrupted_run"]
    assert result["shared_item_elo_updates"] == 2
    assert result["duplicate_after_restore"] == result["first_answer"]
    assert result["summary"]["first_attempts"] == 6
    assert result["summary"]["correct_first_attempts"] == 5
    assert result["summary"]["completed_sessions"] == 2
    assert result["weekly"]["first_attempts"] == 3
    assert result["weekly"]["streak_days"] == 2
