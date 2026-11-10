"""Run the Prediction workflow against synthetic, locally stored Generation fixtures."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neuroknot_ml.service_workflow import PredictionService  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "service_workflow.json"
SUNDAY = "2026-01-04T14:59:00Z"
MONDAY = "2026-01-04T15:00:00Z"


def load_fixtures():
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def _study(service, fixtures, user, exposure_id, timestamp, *, wrong_first=False):
    recommendation = service.recommend(user)
    quiz = recommendation["quiz"]
    clock = {"occurred_at": timestamp, "applied_at": timestamp}
    exposed = service.confirm_exposure(
        user, exposure_id=exposure_id, passage_id=quiz["passage_id"], quiz_version=quiz["quiz_version"], **clock,
    )
    keys = fixtures[quiz["passage_id"]]["quiz"]["questions"]
    first_input = first_result = retry = None
    for index, (question, key) in enumerate(zip(exposed["quiz"]["questions"], keys, strict=True)):
        correct_choice = key["answer_index"]
        answer = {
            "exposure_id": exposure_id, "item_id": question["item_id"], "submission_id": f"{exposure_id}:{index}",
            "choice_index": (correct_choice + 1) % 4 if wrong_first and index == 0 else correct_choice, **clock,
        }
        result = service.submit_answer(user, **answer)
        if index == 0:
            first_input, first_result = answer, result
        if wrong_first and index == 0:
            retry = service.submit_answer(user, **{
                **answer, "submission_id": f"{exposure_id}:retry", "choice_index": correct_choice,
            })
    completion = service.complete_learning(user, exposure_id=exposure_id, **clock)
    return quiz["passage_id"], first_input, first_result, retry, completion


def run_demo() -> dict:
    service = PredictionService()
    fixtures = {}
    for fixture in load_fixtures():
        generated = fixture["generated"]
        fixtures[generated["passage_id"]] = generated
        service.register_quiz(generated, quiz_version="fixture-v1", passage_body=fixture["passage"]["body"])

    first, original, graded, retry, _ = _study(service, fixtures, "alice", "alice-1", SUNDAY, wrong_first=True)
    shared, _, _, _, _ = _study(service, fixtures, "bob", "bob-1", SUNDAY)
    saved = json.loads(json.dumps(service.checkpoint(), allow_nan=False))
    restored = PredictionService.from_checkpoint(saved)
    duplicate = restored.submit_answer("alice", **{**original, "occurred_at": MONDAY, "applied_at": MONDAY})
    count = saved["history"]["model"]["items"][original["item_id"]]["attempts"]
    next_passage, *_ = _study(restored, fixtures, "alice", "alice-2", MONDAY)
    _study(service, fixtures, "alice", "alice-2", MONDAY)
    report = restored.analyze("alice", as_of=MONDAY)
    equivalent = restored.checkpoint() == service.checkpoint() and report == service.analyze("alice", as_of=MONDAY)
    if not (first == shared and first != next_passage and duplicate == graded and count == 2 and equivalent):
        raise RuntimeError("synthetic workflow did not reproduce the expected shared learning state")

    return {
        "data": "synthetic_test_fixtures",
        "first_passage": first,
        "shared_passage": shared,
        "first_answer": graded,
        "retry": retry,
        "duplicate_after_restore": duplicate,
        "shared_item_elo_updates": count,
        "restored_from_sequence": saved["history"]["through_sequence"],
        "next_passage": next_passage,
        "final_sequence": report["through_sequence"],
        "matches_uninterrupted_run": equivalent,
        "summary": report["summary"],
        "weekly": report["weekly"],
        "skills": report["skills"],
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, allow_nan=False, indent=2))
