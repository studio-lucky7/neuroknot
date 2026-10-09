"""문항·해설 데이터 형식.

이 형식이 곧 모델에게 요구하는 출력 형식이자, 나중에 DB `questions` 테이블의
컬럼이 된다. 앱으로 내려보낼 때는 `answer_index`를 반드시 제외한다.
"""

from pydantic import BaseModel, Field

from .skills import ErrorType, Skill


class Passage(BaseModel):
    """입력 지문. gen/fixtures/*.json 과 같은 구조이며,
    나중에 슬라이스 1이 채우는 `passages` 테이블과도 같다."""

    id: str
    title: str
    category: str
    source: str
    source_url: str
    license: str
    body: str


class Distractor(BaseModel):
    """틀린 선택지 하나에 대한 설명."""

    option_index: int = Field(ge=0, le=3, description="이 설명이 가리키는 선택지 번호")
    why_wrong: str = Field(description="이 선택지가 왜 틀렸는지 지문을 근거로 한 설명")
    error_type: ErrorType = Field(
        description="이 선택지가 유도하도록 설계된 오류 유형 (출제 의도이며, 학습자가 실제로 그렇게 틀렸다는 확정은 아니다)"
    )


class Question(BaseModel):
    """문항 하나 + 선택지별 해설."""

    skill: Skill = Field(description="이 문항이 측정하는 능력")
    stem: str = Field(description="문제 문장")
    options: list[str] = Field(min_length=4, max_length=4, description="선택지 4개")
    answer_index: int = Field(ge=0, le=3, description="정답 선택지 번호")
    evidence: str = Field(description="지문에서 그대로 인용한 근거 문장")
    explanation: str = Field(description="정답이 왜 정답인지에 대한 해설")
    distractors: list[Distractor] = Field(
        min_length=3, max_length=3, description="정답을 제외한 선택지 3개에 대한 설명"
    )


class QuizSet(BaseModel):
    """지문 한 편에서 만든 문항 묶음."""

    difficulty_hint: int = Field(
        ge=1, le=5, description="지문 자체의 체감 난이도 (1 쉬움 ~ 5 어려움)"
    )
    questions: list[Question] = Field(
        min_length=3, max_length=3, description="서로 다른 스킬을 측정하는 문항 3개"
    )


class GeneratedQuiz(BaseModel):
    """저장 단위. 생성 결과에 어떤 지문/프롬프트/모델에서 나왔는지를 함께 남긴다.

    프롬프트를 고친 뒤 '어떤 문항이 옛 버전으로 만들어졌는지' 추적하려면
    prompt_version 이 반드시 필요하다.
    """

    passage_id: str
    prompt_version: str
    model: str
    quiz: QuizSet
