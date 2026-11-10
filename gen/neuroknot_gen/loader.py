"""샘플 지문 읽기.

나중에 슬라이스 1의 `passages` 테이블이 생기면 이 파일만 DB 조회로 바꾸면 된다.
나머지 코드는 Passage 객체만 알면 되므로 손대지 않는다.
"""

import json
from pathlib import Path

from .schemas import Passage

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def load_passage(passage_id: str) -> Passage:
    path = FIXTURE_DIR / f"{passage_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"지문을 찾을 수 없습니다: {path}")
    return Passage.model_validate_json(path.read_text(encoding="utf-8"))


def load_all_passages() -> list[Passage]:
    return [
        Passage.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(FIXTURE_DIR.glob("fx-*.json"))
    ]
