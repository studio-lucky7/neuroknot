"""지문의 카테고리를 정한다. (2단계)

부처로 후보를 좁히고, 후보가 둘 이상일 때만 모델에게 본문을 읽혀 고르게 한다.
기관은 기사에 적혀 있는 **사실**이므로 울타리로 쓸 수 있다. 모델이 울타리 밖 답을
내면 그 답을 버린다. 그래서 "문체부 기사가 컴퓨터/IT 로 분류되는" 사고가 없다.

후보가 하나뿐이면 모델을 아예 부르지 않는다. 호출 수와 비용이 그만큼 줄어든다.

모델은 수민 님 슬라이스와 같은 Google Gemini 를 쓴다.
다른 회사 모델로 바꾸려면 이 파일만 고치면 된다.
"""

import os

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from .categories import CATEGORY_LABELS
from .ministries import candidates_for
from .sources.base import RawArticle

DEFAULT_MODEL = "gemini-3.8-flash"
MAX_OUTPUT_TOKENS = 500

SYSTEM_PROMPT = """당신은 한국어 읽기 훈련 앱에 들어갈 지문을 분류합니다.

주어진 글을 읽고, 제시된 후보 카테고리 중 **글의 중심 내용에 가장 가까운 하나**를 고르십시오.

판단 기준
- 글을 쓴 기관이 아니라 **글이 다루는 내용**으로 고릅니다.
- 소재가 여러 개면 글 전체를 관통하는 주제를 따릅니다.
- 반드시 후보 안에서만 고릅니다. 후보에 없는 값을 쓰면 안 됩니다.
- **후보 중 어느 것도 글의 중심 내용과 맞지 않으면 "none" 이라고 답하십시오.**
  억지로 가장 비슷해 보이는 것을 고르면 안 됩니다. 버리는 편이 낫습니다.
  예: 저작권 제도를 다루는 글에 후보가 예술·패션·문학·인문뿐이라면 "none" 입니다.
"""


class CategoryChoice(BaseModel):
    """모델이 돌려줄 형식."""

    category: str = Field(description='후보 중에서 고른 카테고리 ID. 맞는 것이 없으면 "none"')
    reason: str = Field(description="그렇게 고른 이유 한 문장")


class ClassifyResult(BaseModel):
    """분류 결과. category 가 None 이면 정하지 못한 것이다."""

    category: str | None
    reason: str
    used_model: bool = Field(description="모델을 실제로 불렀는지")


def model_name() -> str:
    """.env 의 GEMINI_MODEL 로 바꿀 수 있다."""
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def make_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY가 없습니다. rec/.env 에 키를 넣고 다시 실행하세요."
        )
    return genai.Client(api_key=api_key)


def build_user_content(article: RawArticle, candidates: list[str]) -> str:
    lines = ["<후보>"]
    lines += [f"- {cid}: {CATEGORY_LABELS[cid]}" for cid in candidates]
    lines += ["</후보>", "", "<글>", f"제목: {article.title}", "", article.body, "</글>"]
    return "\n".join(lines)


def classify(article: RawArticle, *, client: genai.Client | None = None) -> ClassifyResult:
    candidates = sorted(candidates_for(article.publisher))

    if not candidates:
        return ClassifyResult(
            category=None,
            reason=f"표에 없는 기관이라 건너뜁니다 → {article.publisher!r}",
            used_model=False,
        )

    if len(candidates) == 1:
        return ClassifyResult(
            category=candidates[0],
            reason="후보가 하나뿐이라 모델을 부르지 않았습니다",
            used_model=False,
        )

    client = client or make_client()
    try:
        response = client.models.generate_content(
            model=model_name(),
            contents=build_user_content(article, candidates),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=CategoryChoice,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
    except Exception as error:  # 네트워크·인증·한도 초과 등
        return ClassifyResult(
            category=None,
            reason=f"호출 실패: {type(error).__name__}: {str(error)[:120]}",
            used_model=True,
        )

    choice = response.parsed
    if choice is None:
        return ClassifyResult(
            category=None, reason="정해진 형식으로 답을 받지 못했습니다", used_model=True
        )
    if not isinstance(choice, CategoryChoice):  # 혹시 dict 로 올 경우 대비
        choice = CategoryChoice.model_validate(choice)

        # ── 울타리 검사 ──
    # 후보 중 맞는 것이 없으면 "none" 으로 답하도록 지시해 두었다.
    # 억지로 하나를 고르게 하면 저작권 정책 기사가 언어/문학으로 들어가는 일이 생긴다.
    if choice.category == "none":
        return ClassifyResult(
            category=None,
            reason=f"후보 중 맞는 것이 없습니다 → {choice.reason}",
            used_model=True,
        )

    # 후보 밖 답도 버린다. 억지로 끼워 넣지 않는다.
    if choice.category not in candidates:
        return ClassifyResult(
            category=None,
            reason=f"후보 밖 답이라 버립니다 → {choice.category!r}",
            used_model=True,
        )

    return ClassifyResult(category=choice.category, reason=choice.reason, used_model=True)