"""수집한 지문이 팀 기준을 만족하는지 기계가 먼저 거르는 검사.

기준은 `gen/fixtures/README.md` 의 '지문을 더 추가할 때' 절에서 가져왔다.
사람이 읽어야 아는 것(글 전체를 관통하는 주장이 있는가 등)은 여기서 보지 않는다.
여기서 보는 것은 **세면 알 수 있는 것**뿐이다. 108편을 눈으로 확인하지 않기 위한 장치다.

글자 수는 README 의 표와 같은 기준, 즉 공백·줄바꿈을 포함한 len(body) 다.
fx-001~005 로 대조해 773/1429/882/1249/1798 자가 그대로 나오는 것을 확인했다.
"""

import re

from .categories import CATEGORY_IDS
from .schemas import Passage

MIN_CHARS = 600
MAX_CHARS = 2000
MIN_PARAGRAPHS = 3

# 상업적 이용과 변형이 모두 가능한 조건만 받는다.
# 공공누리 제2·4유형은 상업 금지, 제3·4유형은 변경 금지라 청킹을 할 수 없으므로 제외한다.
ALLOWED_LICENSES = frozenset({"KOGL-1"})


def paragraphs(body: str) -> list[str]:
    """빈 줄로 나눈 문단. 앱의 읽기 화면도 같은 기준으로 나눈다."""
    return [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


def check_text(title: str, body: str, license_id: str) -> list[str]:
    """카테고리를 빼고 글 자체만 보는 검사.

    수집 단계(RawArticle)에서는 카테고리가 아직 없으므로 이쪽을 쓴다.
    """
    problems: list[str] = []

    if license_id not in ALLOWED_LICENSES:
        problems.append(f"허용되지 않은 이용 조건입니다 → {license_id!r}")

    n = len(body)
    if not MIN_CHARS <= n <= MAX_CHARS:
        problems.append(f"분량이 {MIN_CHARS}~{MAX_CHARS}자를 벗어납니다 → {n}자")

    paras = paragraphs(body)
    if len(paras) < MIN_PARAGRAPHS:
        problems.append(f"문단이 {MIN_PARAGRAPHS}개 미만입니다 → {len(paras)}개")

    # 수치가 없으면 fact 문항을 만들 근거가 부족하다.
    if not re.search(r"\d", body):
        problems.append("본문에 수치가 없습니다. fact 문항을 만들기 어렵습니다.")

    if not title.strip():
        problems.append("title 이 비어 있습니다.")

    # 본문은 고치지 않는다. 앞뒤 공백이 남았다면 수집기의 추출 범위를 고쳐야 한다.
    if body != body.strip():
        problems.append("본문 앞뒤에 불필요한 공백이 남아 있습니다. 수집기를 고치세요.")

    return problems


def check_passage(p: Passage) -> list[str]:
    """지문 하나가 기준을 만족하는지. 빈 목록이면 통과. (2단계 이후에 쓴다)"""
    problems = check_text(p.title, p.body, p.license)

    if p.category not in CATEGORY_IDS:
        problems.append(f"카테고리가 9개 목록에 없습니다 → {p.category!r}")

    for field in ("id", "source", "source_url"):
        if not getattr(p, field).strip():
            problems.append(f"{field} 가 비어 있습니다.")

    return problems