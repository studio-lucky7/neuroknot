"""대한민국 정책브리핑(korea.kr) 수집기.

주소 목록은 사이트맵에서 받는다. 목록 페이지는 페이지 넘기기가 자바스크립트라
긁기 까다롭지만, 사이트맵은 사이트가 스스로 공개한 XML 이라 그냥 읽으면 된다.
robots.txt 는 모든 경로를 허용하지만 Crawl-delay 가 없으므로 예의상 간격을 둔다.
(간격은 scripts/run_collect.py 에서 준다.)

본문 추출 규칙은 fx-001(수민 님이 손으로 만든 지문)과 글자 단위로 대조해
완전히 같은 결과가 나오는 것을 확인하고 정했다.

  - 문단은 `.article_body .view_cont` 의 **직계 <p> 만** 쓴다.
    사진 설명은 <div class="imageWrap"> 안에 있어서 자동으로 빠진다.
    사진 설명에는 "(ⓒ뉴스1, 무단 전재-재배포 금지)" 처럼 **남의 저작물 표시**가
    들어 있다. 절대 본문에 섞이면 안 된다.
  - 끝의 "문의: ..." 와 "<자료출처=..." 줄은 지문이 아니므로 뺀다.
"""

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator

import requests
from bs4 import BeautifulSoup

from .base import RawArticle

SITEMAP_URL = "https://www.korea.kr/sitemap_policy.xml"
SOURCE_NAME = "대한민국 정책브리핑"
LICENSE_ID = "KOGL-1"

# 이 문구가 본문 아래에 있는 기사만 쓴다. 없으면 자유이용 대상이 아니다.
KOGL_MARK = "공공누리 제1유형"

# 지문이 아닌 꼬리말
FOOTER_PREFIXES = ("문의:", "<자료출처")

DATE = re.compile(r"\d{4}\.\d{2}\.\d{2}")
NEWS_ID = re.compile(r"newsId=(\d+)")

HEADERS = {"User-Agent": "neuroknot-passage-collector/0.1"}
TIMEOUT = 20


class KoreaKrSource:
    name = "korea_kr"

    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def iter_article_urls(self) -> Iterator[str]:
        """사이트맵에서 정책뉴스 주소를 차례로 내놓는다."""
        res = self.session.get(SITEMAP_URL, timeout=TIMEOUT)
        res.raise_for_status()
        root = ET.fromstring(res.content)
        # 사이트맵 XML 은 태그마다 이름공간이 붙는다. 끝이 'loc' 인 태그만 고른다.
        for el in root.iter():
            if el.tag.endswith("loc"):
                url = (el.text or "").strip()
                if "policyNewsView.do" in url:
                    yield url

    def fetch(self, url: str) -> RawArticle | None:
        res = self.session.get(url, timeout=TIMEOUT)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # 이용 조건부터 본다. 자유이용 표시가 없으면 더 볼 것도 없다.
        footer = soup.select_one(".article_footer")
        if footer is None or KOGL_MARK not in footer.get_text():
            return None

        title_el = soup.select_one("h1")
        cont = soup.select_one(".article_body .view_cont")
        if title_el is None or cont is None:
            return None

        paragraphs = []
        for p in cont.find_all("p", recursive=False):
            text = p.get_text(" ", strip=True)
            if text and not text.startswith(FOOTER_PREFIXES):
                paragraphs.append(text)
        if not paragraphs:
            return None

        spans = soup.select(".article_head .info > span")
        found = DATE.search(spans[0].get_text(" ", strip=True)) if spans else None
        published_at = found.group(0) if found else ""

        # 기관명은 두 가지 모양으로 나온다.
        #  1) 부처가 낸 기사: <a class="gotosite">부처명<i>부처별 뉴스 이동</i></a>
        #     <i> 안의 안내 문구가 섞이지 않도록 **직계 텍스트만** 읽는다.
        #  2) 정책브리핑 기자가 쓴 기사: 링크 없이 <span>정책브리핑</span> 만 있다.
        #     소관 부처가 없는 기사이므로 "정책브리핑" 이 그대로 들어간다.
        goto = soup.select_one(".article_head .info a.gotosite")
        if goto is not None:
            publisher = "".join(goto.find_all(string=True, recursive=False)).strip()
        elif len(spans) >= 2:
            publisher = spans[1].get_text(" ", strip=True)
        else:
            publisher = ""

        news_id = NEWS_ID.search(url)
        return RawArticle(
            source_id=news_id.group(1) if news_id else url,
            title=title_el.get_text(" ", strip=True),
            body="\n\n".join(paragraphs),
            source=f"{SOURCE_NAME} ({publisher})" if publisher else SOURCE_NAME,
            source_url=url,
            license=LICENSE_ID,
            publisher=publisher,
            published_at=published_at,
        )