"""슬라이스 2 API: 문제 조회 → 답안 제출(채점) → 해설 조회.

앱 화면(reading.tsx) 흐름과 그대로 맞춘다.
  읽기 완료 → GET  /gen/passages/{id}/quiz        문제 받기 (정답 없음)
  정답 확인 → POST /gen/attempts                   서버가 채점, 맞았는지만 알려 줌
  해설 보기 → GET  /gen/attempts/{id}/explanation  이때 정답과 해설 공개

FastAPI 읽는 법
- `@router.get(...)` 위의 경로로 요청이 오면 바로 아래 함수가 실행된다.
- 함수 인자 중 경로에 있는 이름(passage_id 등)은 URL에서, Pydantic 모델(AttemptIn)은
  요청 본문(JSON)에서 자동으로 꺼내고 형식 검사까지 해 준다. 형식이 틀리면 422.
- `Depends(get_quiz_store)`는 '이 함수를 불러서 나온 값을 넣어 달라'는 뜻이다.
  테스트에서는 이 함수를 가짜로 바꿔 끼워서 실제 파일 없이도 돌릴 수 있다.
- `response_model`에 적은 형식에 없는 값은 응답에서 잘려 나간다.
"""

import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from .models import (
    AttemptIn,
    AttemptOut,
    ExplanationOut,
    QuestionView,
    QuizView,
    SelectedFeedback,
)
from .store import AttemptStore, QuizStore, quiz_dir_from_env

router = APIRouter(prefix="/gen", tags=["gen"])

# 지문 ID는 파일 이름으로도 쓰이므로 글자·숫자·-·_ 만 허용한다.
# 이렇게 막지 않으면 "../../.env" 같은 값으로 다른 파일을 읽으려 할 수 있다.
PassageId = Annotated[
    str, Path(pattern=r"^[A-Za-z0-9_-]+$", max_length=64, examples=["fx-001"])
]


@lru_cache
def get_quiz_store() -> QuizStore:
    return QuizStore(quiz_dir_from_env())


@lru_cache
def get_attempt_store() -> AttemptStore:
    # lru_cache 덕분에 서버가 떠 있는 동안 같은 저장소 하나를 계속 쓴다.
    return AttemptStore()


QuizStoreDep = Annotated[QuizStore, Depends(get_quiz_store)]
AttemptStoreDep = Annotated[AttemptStore, Depends(get_attempt_store)]


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what}을(를) 찾을 수 없습니다")


@router.get("/passages/{passage_id}/quiz", response_model=QuizView)
def get_quiz(passage_id: PassageId, quizzes: QuizStoreDep) -> QuizView:
    generated = quizzes.get(passage_id)
    if generated is None:
        raise _not_found("이 지문의 문항")

    return QuizView(
        passage_id=generated.passage_id,
        difficulty_hint=generated.quiz.difficulty_hint,
        questions=[
            QuestionView(question_index=i, skill=q.skill, stem=q.stem, options=q.options)
            for i, q in enumerate(generated.quiz.questions)
        ],
    )


@router.post("/attempts", response_model=AttemptOut, status_code=status.HTTP_201_CREATED)
def submit_attempt(body: AttemptIn, quizzes: QuizStoreDep, attempts: AttemptStoreDep) -> AttemptOut:
    generated = quizzes.get(body.passage_id)
    if generated is None:
        raise _not_found("이 지문의 문항")

    questions = generated.quiz.questions
    if body.question_index >= len(questions):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"question_index는 0~{len(questions) - 1} 사이여야 합니다",
        )

    question = questions[body.question_index]
    correct = body.selected_index == question.answer_index

    # 오답이면 '그 선택지가 유도하도록 설계된 오류 유형'을 함께 남긴다 (슬라이스 3용).
    intended = None
    if not correct:
        intended = next(
            d.error_type for d in question.distractors if d.option_index == body.selected_index
        )

    record = attempts.add(
        attempt_id=uuid.uuid4().hex,
        user_id=body.user_id,
        passage_id=body.passage_id,
        question_index=body.question_index,
        skill=question.skill,
        selected_index=body.selected_index,
        correct=correct,
        intended_error_type=intended,
        prompt_version=generated.prompt_version,
        created_at=datetime.now(timezone.utc),
    )
    return AttemptOut(attempt_id=record.attempt_id, correct=correct, try_number=record.try_number)


@router.get("/attempts/{attempt_id}/explanation", response_model=ExplanationOut)
def get_explanation(attempt_id: str, quizzes: QuizStoreDep, attempts: AttemptStoreDep) -> ExplanationOut:
    record = attempts.get(attempt_id)
    if record is None:
        raise _not_found("답안 기록")

    generated = quizzes.get(record.passage_id)
    if generated is None:
        raise _not_found("이 지문의 문항")
    question = generated.quiz.questions[record.question_index]

    feedback = None
    if not record.correct:
        why = next(d.why_wrong for d in question.distractors if d.option_index == record.selected_index)
        feedback = SelectedFeedback(why_wrong=why)

    return ExplanationOut(
        attempt_id=record.attempt_id,
        correct=record.correct,
        selected_index=record.selected_index,
        answer_index=question.answer_index,
        explanation=question.explanation,
        evidence=question.evidence,
        selected_feedback=feedback,
    )
