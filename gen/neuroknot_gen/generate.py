"""Gemini로 문항·해설을 만든다.

설계 메모
- 이 호출은 **지문 한 편당 한 번만** 일어난다. 사용자가 앱에서 답을 고를 때는
  모델을 부르지 않고 여기서 만들어 둔 결과를 조회하기만 한다.
- 출제 지침(프롬프트)은 지문이 바뀌어도 그대로이므로 system_instruction에 두고,
  지문마다 달라지는 내용만 contents로 보낸다.
- `response_schema`에 schemas.QuizSet(Pydantic)을 그대로 넘기면 모델이 그 형식으로만
  답한다. 다만 "선택지 정확히 4개" 같은 세부 제약까지 강제되지는 않으므로,
  받은 뒤에 validate.py로 반드시 한 번 더 검사한다.

모델을 다른 회사 것으로 바꾸려면 이 파일만 고치면 된다.
(schemas / validate / loader / prompts / run_generate 는 그대로 쓸 수 있다.)
"""

import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types

from .schemas import GeneratedQuiz, Passage, QuizSet
from .shuffle import shuffle_quiz
from .skills import Skill

DEFAULT_MODEL = "gemini-3.8-flash"
MAX_OUTPUT_TOKENS = 16000
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_PROMPT_VERSION = "quiz_v2"

# 스킬 조합을 모델이 스스로 고르던 버전. 이 버전들은 <출제할 능력>을 보내지 않는다.
# (v2는 30문항 중 vocab 0개 — 모델은 늘 fact·inference·main_idea를 골랐다)
MODEL_PICKS_SKILLS = {"quiz_v1", "quiz_v2"}


def assigned_skills(passage_id: str) -> list[Skill]:
    """이 지문에서 출제할 스킬 3개. 네 스킬 중 하나를 지문 ID로 정해 뺀다.

    지문 ID만으로 정해지므로 다시 생성해도 같은 조합이 나오고, 지문이 많아지면
    네 스킬이 각각 약 3/4의 지문에 고르게 나온다. (슬라이스 3이 스킬별 실력을 추정하려면
    모든 스킬의 풀이 기록이 쌓여야 한다.)
    """
    skills = list(Skill)
    digest = hashlib.sha256(passage_id.encode("utf-8")).digest()
    skills.pop(int.from_bytes(digest[:8], "big") % len(skills))
    return skills


def skills_for(passage_id: str, prompt_version: str) -> list[Skill] | None:
    """프롬프트 버전에 따라 출제할 스킬을 정한다. 모델이 고르는 옛 버전이면 None."""
    return None if prompt_version in MODEL_PICKS_SKILLS else assigned_skills(passage_id)


def model_name() -> str:
    """.env 의 GEMINI_MODEL 로 바꿀 수 있다. 쓸 수 있는 이름은
    `python scripts/check_setup.py` 로 확인한다."""
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL  # 빈 값이면 기본값


def make_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY가 없습니다. gen/.env 에 키를 넣고 다시 실행하세요. "
            "(.env.example 참고)"
        )
    return genai.Client(api_key=api_key)


def load_prompt(version: str = DEFAULT_PROMPT_VERSION) -> str:
    path = PROMPT_DIR / f"{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"프롬프트 파일이 없습니다: {path}")
    return path.read_text(encoding="utf-8")


def build_user_content(
    passage: Passage,
    retry_notes: list[str] | None = None,
    skills: list[Skill] | None = None,
) -> str:
    parts = [
        "<지문>",
        f"제목: {passage.title}",
        f"분야: {passage.category}",
        "",
        passage.body,
        "</지문>",
    ]
    if skills:
        parts += [
            "",
            "<출제할 능력>",
            "문항 3개를 아래 순서대로, 하나씩 이 능력을 측정하도록 만드십시오.",
            *(f"{i}. {s.value}" for i, s in enumerate(skills, 1)),
            "</출제할 능력>",
        ]
    if retry_notes:
        parts += [
            "",
            "<이전 시도의 문제점>",
            "아래 문제를 고쳐서 다시 만드십시오.",
            *(f"- {n}" for n in retry_notes),
            "</이전 시도의 문제점>",
        ]
    return "\n".join(parts)


def _explain_api_error(error: Exception, model: str) -> str:
    """원인별로 무엇을 고쳐야 하는지 한 줄로 알려 준다."""
    text = str(error)
    low = text.lower()

    if "not found" in low or "404" in low:
        hint = (
            f"'{model}' 모델을 찾을 수 없습니다. "
            "`python scripts/check_setup.py` 로 쓸 수 있는 이름을 확인한 뒤 "
            ".env 의 GEMINI_MODEL 에 넣으세요."
        )
    elif "api key" in low or "unauthenticated" in low or "401" in low or "403" in low:
        hint = "API 키가 올바르지 않습니다. gen/.env 의 GEMINI_API_KEY 값을 확인하세요."
    elif "429" in low or "quota" in low or "resource_exhausted" in low:
        hint = "요청 한도를 넘었습니다. 잠시 뒤에 다시 실행하거나 사용량을 확인하세요."
    elif "deadline" in low or "timeout" in low or "connection" in low:
        hint = "네트워크 연결에 실패했습니다. 인터넷 상태를 확인하고 다시 실행하세요."
    else:
        hint = "호출에 실패했습니다."

    return f"{hint}\n  (원래 오류: {type(error).__name__}: {text[:300]})"


def generate_quiz(
    passage: Passage,
    *,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    retry_notes: list[str] | None = None,
    client: genai.Client | None = None,
) -> GeneratedQuiz:
    client = client or make_client()
    model = model_name()
    skills = skills_for(passage.id, prompt_version)

    try:
        response = client.models.generate_content(
            model=model,
            contents=build_user_content(passage, retry_notes, skills),
            config=types.GenerateContentConfig(
                system_instruction=load_prompt(prompt_version),
                response_mime_type="application/json",
                response_schema=QuizSet,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
    except Exception as e:  # 네트워크·인증·모델 이름 등 호출 자체의 실패
        raise RuntimeError(_explain_api_error(e, model)) from e

    quiz = response.parsed
    if quiz is None:
        # 안전 필터에 걸리거나 형식을 못 맞춘 경우
        reason = getattr(response, "prompt_feedback", None)
        raise RuntimeError(
            f"정해진 형식으로 응답을 받지 못했습니다. (model={model}, feedback={reason})"
        )
    if not isinstance(quiz, QuizSet):  # 혹시 dict로 올 경우 대비
        quiz = QuizSet.model_validate(quiz)

    # 요소별 점수가 있으면 난이도는 그 합계로 정한다 (모델이 쓴 1~5보다 이쪽을 믿는다)
    if quiz.difficulty_factors is not None:
        quiz = quiz.model_copy(update={"difficulty_hint": quiz.difficulty_factors.to_hint()})

    # 모델은 정답을 앞쪽에 몰아 두는 경향이 있어 코드로 자리를 섞는다
    quiz = shuffle_quiz(quiz, seed=passage.id)

    return GeneratedQuiz(
        passage_id=passage.id,
        # 재시도도 새 생성이므로 호출할 때마다 새 ID를 붙인다
        quiz_id=uuid.uuid4().hex,
        generated_at=datetime.now(timezone.utc),
        prompt_version=prompt_version,
        model=model,
        quiz=quiz,
    )
