"""지문 카테고리 9개.

`frontend/src/constants/categories.ts` 와 **반드시 같아야 한다.**
온보딩에서 사용자가 고른 카테고리로 지문을 찾기 때문에, ID 가 하나라도 어긋나면
그 카테고리를 고른 사용자에게 추천할 지문이 0건이 된다.
카테고리 ID 는 공통 기반이므로, 바꿀 때는 협업 가이드 6절에 따라 팀 합의가 필요하다.
"""

CATEGORY_LABELS = {
    # STEM
    "comp_tech": "컴퓨터/IT",
    "natural_sci": "자연과학",
    "applied_eng": "기술/공학",
    # 인문사회
    "econ_mgmt": "경제/경영",
    "soc_politic": "사회/정치",
    "human_phil": "인문/철학",
    # 예술문화
    "visual_art": "예술/디자인",
    "fash_style": "패션/미학",
    "lit_culture": "언어/문학",
}

CATEGORY_IDS = frozenset(CATEGORY_LABELS)


def category_label(category_id: str) -> str:
    """사람이 읽는 이름. 모르는 ID 는 그대로 돌려준다 (프론트의 categoryLabel 과 같은 동작)."""
    return CATEGORY_LABELS.get(category_id, category_id)