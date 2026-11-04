"""데이터를 어디서 읽고 어디에 쓰는가.

지금은 DB가 없어서 임시로 이렇게 둔다.
- 문항: `run_generate.py`가 만든 JSON 파일(gen/out/)을 읽는다.
- 답안 기록: 메모리에 쌓는다. 서버를 끄면 사라진다.

DB가 생기면 이 파일의 두 클래스만 바꾸면 된다. 라우터(routes.py)는
`get(...)`, `add(...)` 같은 메서드 이름만 알기 때문에 손댈 필요가 없다.
"""

import os
import threading
from pathlib import Path

from ..schemas import GeneratedQuiz
from .models import AttemptRecord

DEFAULT_QUIZ_DIR = Path(__file__).resolve().parents[2] / "out"


class QuizStore:
    """미리 생성해 둔 문항 묶음을 지문 ID로 찾는다."""

    def __init__(self, quiz_dir: Path):
        self.quiz_dir = quiz_dir

    def get(self, passage_id: str) -> GeneratedQuiz | None:
        path = self.quiz_dir / f"{passage_id}.json"
        if not path.is_file():
            return None
        return GeneratedQuiz.model_validate_json(path.read_text(encoding="utf-8"))


class AttemptStore:
    """답안 기록. 요청이 동시에 들어와도 순서가 꼬이지 않도록 잠금을 건다."""

    def __init__(self):
        self._records: dict[str, AttemptRecord] = {}
        self._lock = threading.Lock()

    def add(self, **fields) -> AttemptRecord:
        """기록을 하나 추가하고, 몇 번째 시도인지(try_number)를 붙여 돌려준다.

        '세기'와 '저장'을 한 번의 잠금 안에서 해야 같은 문항에 답이 동시에 두 개
        들어왔을 때 둘 다 1번째 시도로 기록되는 일이 없다.
        """
        with self._lock:
            key = (fields["user_id"], fields["passage_id"], fields["question_index"])
            earlier = sum(
                1
                for r in self._records.values()
                if (r.user_id, r.passage_id, r.question_index) == key
            )
            record = AttemptRecord(**fields, try_number=earlier + 1)
            self._records[record.attempt_id] = record
            return record

    def get(self, attempt_id: str) -> AttemptRecord | None:
        with self._lock:
            return self._records.get(attempt_id)


def quiz_dir_from_env() -> Path:
    """GEN_QUIZ_DIR가 있으면 그 폴더, 없으면 gen/out/."""
    value = os.environ.get("GEN_QUIZ_DIR")
    return Path(value) if value else DEFAULT_QUIZ_DIR
