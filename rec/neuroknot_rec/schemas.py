"""지문 데이터 형식.

슬라이스 2(gen/neuroknot_gen/schemas.py)의 Passage 와 **필드 이름·개수가 같아야 한다.**
이 7개가 그대로 passages 테이블의 컬럼이 된다.
바꾸려면 협업 가이드 6절에 따라 [공통] PR 과 나머지 두 명의 승인이 필요하다.
"""

from pydantic import BaseModel, Field


class Passage(BaseModel):
    """수집한 지문 한 편. gen/fixtures/*.json 과 같은 구조다."""

    id: str = Field(description="지문 ID. 예: kr-0001")
    title: str = Field(description="문서 제목")
    category: str = Field(description="categories.py 의 9개 중 하나")
    source: str = Field(description="사람이 읽는 출처 이름. 예: 대한민국 정책브리핑 (문화체육관광부)")
    source_url: str = Field(description="원문 주소")
    license: str = Field(description="이용 조건. 예: KOGL-1")
    body: str = Field(
        description="본문. 문단 구분은 빈 줄(\\n\\n). 원문 오탈자 포함해 절대 가공하지 않는다"
    )