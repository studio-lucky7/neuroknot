"""API가 앱 화면 흐름대로 동작하는지 확인한다.

실제 gen/out/ 파일이나 Gemini 없이 돌도록, 테스트용 임시 폴더에 문항을 하나 써 두고
`dependency_overrides`로 저장소를 바꿔 끼운다.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neuroknot_gen.api.main import app  # noqa: E402
from neuroknot_gen.api.routes import get_attempt_store, get_quiz_store  # noqa: E402
from neuroknot_gen.api.store import AttemptStore, QuizStore  # noqa: E402
from neuroknot_gen.loader import load_passage  # noqa: E402
from neuroknot_gen.schemas import GeneratedQuiz  # noqa: E402

from test_validate import make_quiz  # noqa: E402

PID = "fx-001"


@pytest.fixture
def quiz():
    return make_quiz(load_passage(PID))  # 정답은 세 문항 모두 1번(index 1)


@pytest.fixture
def client(tmp_path, quiz):
    generated = GeneratedQuiz(passage_id=PID, prompt_version="test", model="test", quiz=quiz)
    (tmp_path / f"{PID}.json").write_text(generated.model_dump_json(), encoding="utf-8")

    app.dependency_overrides[get_quiz_store] = lambda: QuizStore(tmp_path)
    attempts = AttemptStore()  # 테스트마다 새 기록
    app.dependency_overrides[get_attempt_store] = lambda: attempts
    yield TestClient(app)
    app.dependency_overrides.clear()


def submit(client, selected, question_index=0, user="u1"):
    return client.post(
        "/gen/attempts",
        json={"user_id": user, "passage_id": PID,
              "question_index": question_index, "selected_index": selected},
    )


# ── 문제 조회 ──


def test_문제_조회에는_정답과_해설이_없다(client):
    res = client.get(f"/gen/passages/{PID}/quiz")
    assert res.status_code == 200
    body = res.json()
    assert len(body["questions"]) == 3
    assert [q["question_index"] for q in body["questions"]] == [0, 1, 2]
    text = res.text
    for secret in ("answer_index", "explanation", "evidence", "distractors", "why_wrong"):
        assert secret not in text


def test_없는_지문은_404(client):
    assert client.get("/gen/passages/fx-999/quiz").status_code == 404


def test_지문_ID로_다른_파일을_읽을_수_없다(client):
    assert client.get("/gen/passages/..%2F.env/quiz").status_code in (404, 422)
    assert client.get("/gen/passages/a.b/quiz").status_code == 422


# ── 답안 제출 ──


def test_정답을_내면_correct(client):
    res = submit(client, selected=1)
    assert res.status_code == 201
    body = res.json()
    assert body["correct"] is True
    assert body["try_number"] == 1
    assert "answer_index" not in body


def test_오답을_내도_정답_번호는_알려주지_않는다(client):
    body = submit(client, selected=0).json()
    assert body["correct"] is False
    assert "answer_index" not in body


def test_다시_풀면_시도_횟수가_늘어난다(client):
    assert submit(client, selected=0).json()["try_number"] == 1
    assert submit(client, selected=1).json()["try_number"] == 2
    # 다른 사용자, 다른 문항은 따로 센다
    assert submit(client, selected=1, user="u2").json()["try_number"] == 1
    assert submit(client, selected=1, question_index=1).json()["try_number"] == 1


def test_오답이면_유도된_오류_유형이_기록된다(client, quiz):
    attempt_id = submit(client, selected=3).json()["attempt_id"]
    store = app.dependency_overrides[get_attempt_store]()
    record = store.get(attempt_id)
    expected = next(d.error_type for d in quiz.questions[0].distractors if d.option_index == 3)
    assert record.intended_error_type == expected
    assert record.skill == quiz.questions[0].skill


@pytest.mark.parametrize("field,value", [
    ("selected_index", 4),
    ("selected_index", -1),
    ("question_index", 3),
    ("user_id", ""),
])
def test_잘못된_답안은_422(client, field, value):
    payload = {"user_id": "u1", "passage_id": PID, "question_index": 0, "selected_index": 1}
    payload[field] = value
    assert client.post("/gen/attempts", json=payload).status_code == 422


def test_없는_지문에_답하면_404(client):
    res = client.post("/gen/attempts", json={
        "user_id": "u1", "passage_id": "fx-999", "question_index": 0, "selected_index": 1})
    assert res.status_code == 404


# ── 해설 조회 ──


def test_오답_해설에는_고른_선택지의_설명이_붙는다(client, quiz):
    attempt_id = submit(client, selected=2).json()["attempt_id"]
    res = client.get(f"/gen/attempts/{attempt_id}/explanation")
    assert res.status_code == 200
    body = res.json()
    q = quiz.questions[0]
    assert body["answer_index"] == q.answer_index
    assert body["explanation"] == q.explanation
    assert body["evidence"] == q.evidence
    expected = next(d.why_wrong for d in q.distractors if d.option_index == 2)
    assert body["selected_feedback"] == {"why_wrong": expected}
    assert "error_type" not in res.text  # 출제 의도 라벨은 학습자에게 보여 주지 않는다


def test_정답_해설에는_오답_설명이_없다(client):
    attempt_id = submit(client, selected=1).json()["attempt_id"]
    body = client.get(f"/gen/attempts/{attempt_id}/explanation").json()
    assert body["correct"] is True
    assert body["selected_feedback"] is None


def test_없는_답안의_해설은_404(client):
    assert client.get("/gen/attempts/nope/explanation").status_code == 404
