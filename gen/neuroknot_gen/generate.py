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

import os
from pathlib import Path

from google import genai
from google.genai import types

from .schemas import GeneratedQuiz, Passage, QuizSet
from .shuffle import shuffle_quiz

DEFAULT_MODEL = "gemini-3.8-flash"
MAX_OUTPUT_TOKENS = 16000
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_PROMPT_VERSION = "quiz_v2"


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


def build_user_content(passage: Passage, retry_notes: list[str] | None = None) -> str:
    parts = [
        "<지문>",
        f"제목: {passage.title}",
        f"분야: {passage.category}",
        "",
        passage.body,
        "</지문>",
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

    try:
        response = client.models.generate_content(
            model=model,
            contents=build_user_content(passage, retry_notes),
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

    # 모델은 정답을 앞쪽에 몰아 두는 경향이 있어 코드로 자리를 섞는다
    quiz = shuffle_quiz(quiz, seed=passage.id)

    return GeneratedQuiz(
        passage_id=passage.id,
        prompt_version=prompt_version,
        model=model,
        quiz=quiz,
    )
