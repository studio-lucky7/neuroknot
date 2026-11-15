"""정책브리핑 기사에 찍히는 기관명 → 그 기관이 낼 만한 카테고리 후보.

카테고리를 하나로 확정하지 않고 **후보 집합**을 돌려주는 것이 핵심이다.
기관은 기사에 실제로 적혀 있는 검증 가능한 사실이므로 울타리로 삼을 수 있다.
후보가 하나면 그대로 확정하고, 둘 이상이면 본문을 읽고 그 안에서만 고른다.
이렇게 하면 분류가 울타리 밖으로 나가는 사고를 원천 차단할 수 있다.

기관 이름은 2026년 11월 15일 정책브리핑 상세검색의 '기관별' 목록
(부처 27 · 청 19 · 위원회 9)을 그대로 옮겼다.
정부 조직 개편으로 이름이 자주 바뀌므로(예: 환경부 → 기후에너지환경부)
**추측하지 말고 반드시 목록에서 확인해 고친다.** 한 글자만 달라도 매칭이 실패하고,
에러 없이 조용히 0건이 되어 원인을 찾기 어렵다.
"""

from .categories import CATEGORY_IDS

MINISTRY_CANDIDATES: dict[str, frozenset[str]] = {
    # ── 부처 ──────────────────────────────────────────────
    "청와대": frozenset({"soc_politic"}),
    "국무조정실": frozenset({"soc_politic"}),
    "고용노동부": frozenset({"soc_politic", "econ_mgmt"}),
    "과학기술정보통신부": frozenset({"comp_tech", "natural_sci", "applied_eng"}),
    "교육부": frozenset({"soc_politic", "human_phil"}),
    "국가데이터처": frozenset({"comp_tech", "soc_politic"}),
    "국가보훈부": frozenset({"soc_politic", "human_phil"}),
    "국방부": frozenset({"soc_politic", "applied_eng"}),
    "국토교통부": frozenset({"applied_eng", "econ_mgmt"}),
    "기획예산처": frozenset({"econ_mgmt", "soc_politic"}),
    "기후에너지환경부": frozenset({"natural_sci", "applied_eng", "soc_politic"}),
    "농림축산식품부": frozenset({"natural_sci", "econ_mgmt"}),
    "문화체육관광부": frozenset({"visual_art", "fash_style", "lit_culture", "human_phil"}),
    "법무부": frozenset({"soc_politic"}),
    "법제처": frozenset({"soc_politic"}),
    "보건복지부": frozenset({"soc_politic", "natural_sci"}),
    "산업통상부": frozenset({"applied_eng", "econ_mgmt"}),
    "성평등가족부": frozenset({"soc_politic"}),
    "식품의약품안전처": frozenset({"natural_sci", "soc_politic"}),
    "외교부": frozenset({"soc_politic"}),
    "인사혁신처": frozenset({"soc_politic"}),
    "재정경제부": frozenset({"econ_mgmt"}),
    "중소벤처기업부": frozenset({"econ_mgmt", "comp_tech"}),
    "지식재산처": frozenset({"econ_mgmt", "comp_tech"}),
    "통일부": frozenset({"soc_politic", "human_phil"}),
    "해양수산부": frozenset({"natural_sci", "econ_mgmt"}),
    "행정안전부": frozenset({"soc_politic"}),
    # ── 청 ────────────────────────────────────────────────
    "경찰청": frozenset({"soc_politic"}),
    "공소청": frozenset({"soc_politic"}),
    "관세청": frozenset({"econ_mgmt"}),
    "국가유산청": frozenset({"human_phil", "visual_art", "lit_culture"}),
    "국세청": frozenset({"econ_mgmt"}),
    "기상청": frozenset({"natural_sci"}),
    "농촌진흥청": frozenset({"natural_sci", "applied_eng"}),
    "방위사업청": frozenset({"applied_eng", "soc_politic"}),
    "병무청": frozenset({"soc_politic"}),
    "산림청": frozenset({"natural_sci"}),
    "새만금개발청": frozenset({"applied_eng", "econ_mgmt"}),
    "소방청": frozenset({"soc_politic", "applied_eng"}),
    "우주항공청": frozenset({"natural_sci", "applied_eng"}),
    "재외동포청": frozenset({"soc_politic"}),
    "조달청": frozenset({"econ_mgmt"}),
    "중대범죄수사청": frozenset({"soc_politic"}),
    "질병관리청": frozenset({"natural_sci", "soc_politic"}),
    "해양경찰청": frozenset({"soc_politic"}),
    "행정중심복합도시건설청": frozenset({"applied_eng", "soc_politic"}),
    # ── 위원회 ────────────────────────────────────────────
    "감사원": frozenset({"soc_politic"}),
    "개인정보보호위원회": frozenset({"comp_tech", "soc_politic"}),
    "공정거래위원회": frozenset({"econ_mgmt", "soc_politic"}),
    "국가인권위원회": frozenset({"soc_politic", "human_phil"}),
    "국민권익위원회": frozenset({"soc_politic"}),
    "금융위원회": frozenset({"econ_mgmt"}),
    "방송미디어통신위원회": frozenset({"comp_tech", "visual_art", "soc_politic"}),
    "원자력안전위원회": frozenset({"natural_sci", "applied_eng"}),
    "중앙선거관리위원회": frozenset({"soc_politic"}),
    # ── 부처가 없는 기사 ──────────────────────────────────
    # 정책브리핑 기자가 직접 쓴 기사. 소관 부처가 없어 울타리가 넓어지므로
    # 일반 정책 뉴스가 다루는 범위로 좁게 준다.
    "정책브리핑": frozenset({"econ_mgmt", "soc_politic"}),
} 

# 표에 오타가 있으면 import 하는 순간 바로 알 수 있게 한다.
# 조용히 틀리는 것보다 시끄럽게 실패하는 쪽이 낫다.
for _ministry, _candidates in MINISTRY_CANDIDATES.items():
    _unknown = _candidates - CATEGORY_IDS
    if _unknown:
        raise ValueError(f"{_ministry}: categories.py 에 없는 카테고리 {sorted(_unknown)}")


def candidates_for(ministry: str) -> frozenset[str]:
    """기관명으로 카테고리 후보를 찾는다. 표에 없는 기관이면 빈 집합을 돌려준다.

    빈 집합이면 그 기사는 분류하지 않고 건너뛴다. 3,400개 중에서 고르는 것이라
    몇 건 버려도 아깝지 않다. 잘못 분류된 지문이 섞이는 쪽이 훨씬 손해다.
    """
    return MINISTRY_CANDIDATES.get(ministry.strip(), frozenset())