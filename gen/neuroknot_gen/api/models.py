"""API 요청·응답 형식.

`schemas.py`는 '생성 결과 전체'(정답·해설 포함)이고, 여기는 '앱과 주고받는 모양'이다.
둘을 나눠 두는 이유: 앱에 내려가는 응답에 정답이 섞여 들어가는 실수를
형식 단계에서 막기 위해서다. `QuestionView`에는 애초에 answer_index 칸이 없다.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from ..skills import ErrorType, Skill

# ── 문제 조회 ────────────────────────────────────────────────


class QuestionView(BaseModel):
    """앱에 보여 주는 문항. 정답·근거·해설은 일부러 뺐다."""

    question_index: int
    skill: Skill
    stem: str
    options: list[str]


class QuizView(BaseModel):
    passage_id: str
    difficulty_hint: int
    questions: list[QuestionView]


# ── 답안 제출 ────────────────────────────────────────────────


class AttemptIn(BaseModel):
    """앱이 보내는 답안 하나.

    user_id는 로그인이 붙기 전까지 앱이 직접 보낸다. 로그인이 생기면
    요청 본문이 아니라 인증 토큰에서 꺼내도록 바꾼다.
    """

    user_id: str = Field(min_length=1, max_length=64, examples=["me"])
    passage_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$", max_length=64, examples=["fx-001"])
    question_index: int = Field(ge=0, examples=[0])
    selected_index: int = Field(ge=0, le=3, examples=[1])


class AttemptOut(BaseModel):
    """채점 결과. 틀렸을 때 '다시 풀기'가 가능하므로 정답 번호는 알려 주지 않는다."""

    attempt_id: str
    correct: bool
    try_number: int = Field(description="같은 사용자가 같은 문항을 몇 번째로 푸는지 (1부터)")


# ── 해설 조회 ────────────────────────────────────────────────


class SelectedFeedback(BaseModel):
    """학습자가 고른 오답에 대한 설명."""

    why_wrong: str


class ExplanationOut(BaseModel):
    """'해설 보기'를 눌렀을 때. 이 시점부터는 정답을 공개한다."""

    attempt_id: str
    correct: bool
    selected_index: int
    answer_index: int
    explanation: str
    evidence: str
    selected_feedback: SelectedFeedback | None = Field(
        description="오답을 골랐을 때만 채워진다"
    )


# ── 저장되는 기록 (슬라이스 3이 읽을 데이터) ─────────────────────


class AttemptRecord(BaseModel):
    """답안 기록 한 줄. 지금은 메모리에만 있고, DB 스키마가 정해지면 테이블로 옮긴다.

    intended_error_type은 '그 오답이 유도하도록 설계된 오류'이지,
    학습자가 실제로 그 실수를 했다는 확정이 아니다 (skills.py 설명 참고).
    """

    attempt_id: str
    user_id: str
    passage_id: str
    question_index: int
    skill: Skill
    selected_index: int
    correct: bool
    try_number: int
    intended_error_type: ErrorType | None
    prompt_version: str
    created_at: datetime
