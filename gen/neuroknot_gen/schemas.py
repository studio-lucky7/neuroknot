"""문항·해설 데이터 형식.

이 형식이 곧 모델에게 요구하는 출력 형식이자, 나중에 DB `questions` 테이블의
컬럼이 된다. 앱으로 내려보낼 때는 `answer_index`를 반드시 제외한다.
"""

from datetime import datetime

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


class DifficultyFactors(BaseModel):
    """지문 난이도를 네 가지 요소로 나눠 0~2점씩 매긴 값 (quiz_v3부터).

    모델에게 1~5를 한 번에 고르게 하면 거의 모든 지문에 2를 줬다. 요소별로 따로
    판단하게 한 뒤 합계로 난이도를 정하면, 판단 근거를 사람이 확인할 수도 있다.
    """

    terms: int = Field(ge=0, le=2, description="전문 용어: 0 거의 없음, 1 있지만 지문에서 풀어 줌, 2 설명 없이 쓰임")
    density: int = Field(ge=0, le=2, description="정보량: 0 수치·기관·조건이 적음, 1 보통, 2 여러 수치·조건을 서로 견줘야 함")
    structure: int = Field(ge=0, le=2, description="문장 구조: 0 한 문장에 정보 하나, 1 보통, 2 한 문장에 조건·예외·인용이 겹침")
    abstraction: int = Field(ge=0, le=2, description="추상도: 0 구체적 사건·행사 소개, 1 제도·절차 설명, 2 원리·인과·논증")

    def to_hint(self) -> int:
        """합계 0~8을 1~5로 옮긴다. 0~1→1, 2~3→2, 4~5→3, 6~7→4, 8→5."""
        return 1 + (self.terms + self.density + self.structure + self.abstraction) // 2


class QuizSet(BaseModel):
    """지문 한 편에서 만든 문항 묶음."""

    # difficulty_hint 앞에 둔다. 모델은 스키마 순서대로 쓰므로, 요소를 먼저 따져 본 뒤 난이도를 쓴다.
    difficulty_factors: DifficultyFactors | None = Field(
        default=None, description="지문 난이도 요소별 점수. 있으면 difficulty_hint는 이 합계로 정해진다"
    )
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

    quiz_id는 생성 한 번마다 새로 붙는 ID다. 같은 지문을 다시 생성하면 내용이 달라지므로
    지문 ID만으로는 어느 결과인지 가릴 수 없다. 사용자에게 내보낼 문항 세트를 확정할 때
    Prediction이 이 값을 받아 확정 버전과 최종 문항 ID를 정한다. (PR #11 논의)
    """

    passage_id: str
    # quiz_id 이전에 만든 파일(eval/runs/v2-base, v3 등)에는 없어서 None으로 읽힌다.
    # 새로 생성하는 결과에는 generate_quiz가 항상 채운다.
    quiz_id: str | None = Field(default=None, description="생성 한 번마다 새로 붙는 ID (32자리 16진수)")
    generated_at: datetime | None = Field(default=None, description="생성 시각 (UTC)")
    prompt_version: str
    model: str
    quiz: QuizSet
