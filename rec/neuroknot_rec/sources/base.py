"""수집처가 지켜야 할 공통 틀.

수집처마다 글을 가져오는 방법은 다르다. 정책브리핑은 HTML 을 뜯어야 하고,
다른 곳은 API 를 쓸 수도 있다. 그래도 **가져온 결과의 모양은 같아야 한다.**
그래야 수집처가 늘어나도 나머지 코드를 손대지 않는다.

여기서 만드는 RawArticle 은 아직 지문이 아니다. 카테고리가 비어 있기 때문이다.
2단계(분류)를 거쳐야 schemas.Passage 가 된다.
"""

from collections.abc import Iterator
from typing import Protocol

from pydantic import BaseModel, Field


class RawArticle(BaseModel):
    """수집만 끝난 기사. 카테고리는 아직 정해지지 않았다."""

    source_id: str = Field(description="수집처 안에서 기사를 구분하는 값. 예: 148972829")
    title: str = Field(description="기사 제목")
    body: str = Field(description="문단을 빈 줄로 이은 본문. 이 뒤로는 절대 가공하지 않는다")
    source: str = Field(description="사람이 읽는 출처 이름")
    source_url: str = Field(description="원문 주소")
    license: str = Field(description="이용 조건. 예: KOGL-1")
    publisher: str = Field(description="분류 울타리로 쓸 기관명. 정책브리핑은 소관 부처")
    published_at: str = Field(description="발행일. 예: 2026.09.30")


class Source(Protocol):
    """수집처 하나가 제공해야 하는 두 가지.

    상속하지 않아도 된다. 아래 두 가지만 갖추면 수집처로 쓸 수 있다.
    (ml/neuroknot_ml/selection.py 의 SelectionModel 과 같은 방식이다.)
    """

    name: str

    def iter_article_urls(self) -> Iterator[str]:
        """수집할 기사 주소를 차례로 내놓는다."""
        ...

    def fetch(self, url: str) -> RawArticle | None:
        """기사 하나를 가져온다. 이용 조건이 안 맞거나 본문을 못 찾으면 None."""
        ...