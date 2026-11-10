"""Elo와 분리된 지문 단위 콘텐츠 선택 정책."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from math import fsum
from typing import Protocol

from .skills import SKILLS


class SelectionModel(Protocol):
    def predict(self, user_id: str, item_id: str) -> float: ...


@dataclass(frozen=True)
class PassageQuestion:
    item_id: str
    skill: str

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ValueError("item_id must be a nonempty string")
        if self.skill not in SKILLS:
            raise ValueError(f"unknown skill: {self.skill!r}")


@dataclass(frozen=True)
class PassageCandidate:
    passage_id: str
    questions: tuple[PassageQuestion, ...]
    difficulty_hint: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.passage_id, str) or not self.passage_id.strip():
            raise ValueError("passage_id must be a nonempty string")
        questions = tuple(self.questions)
        if len(questions) != 3 or any(not isinstance(q, PassageQuestion) for q in questions):
            raise ValueError("a passage must contain three PassageQuestion objects")
        if len({q.item_id for q in questions}) != 3 or len({q.skill for q in questions}) != 3:
            raise ValueError("a passage must contain distinct item IDs and skills")
        hint = self.difficulty_hint
        if hint is not None and (type(hint) is not int or not 1 <= hint <= 5):
            raise ValueError("difficulty_hint must be an integer from 1 to 5 or None")
        object.__setattr__(self, "questions", questions)

    @classmethod
    def from_generated(cls, generated: Mapping, item_ids: Sequence[str]) -> PassageCandidate:
        """GeneratedQuiz JSON과 호출자가 부여한 문항 ID를 문항 순서대로 연결한다."""
        try:
            passage_id = generated["passage_id"]
            quiz = generated["quiz"]
            skills = tuple(question["skill"] for question in quiz["questions"])
            hint = quiz["difficulty_hint"]
        except (KeyError, TypeError) as error:
            raise ValueError("invalid GeneratedQuiz passage_id, quiz or questions") from error
        if isinstance(item_ids, str) or len(item_ids) != 3 or len(skills) != 3:
            raise ValueError("GeneratedQuiz requires exactly three questions and three item IDs")
        return cls(passage_id, tuple(PassageQuestion(i, s) for i, s in zip(item_ids, skills)), hint)


@dataclass(frozen=True)
class SelectionConfig:
    target_p: float = 0.7

    def __post_init__(self) -> None:
        if not 0 < self.target_p < 1:
            raise ValueError("target_p must be between 0 and 1")


@dataclass(frozen=True)
class PassageScores:
    probabilities: tuple[float, ...]
    mean_probability: float
    target_p: float
    target_distance: float
    total_score: float


@dataclass(frozen=True)
class SelectionResult:
    passage: PassageCandidate | None
    scores: PassageScores | None
    reasons: tuple[str, ...]
    eligible_count: int
    excluded_seen: int
    excluded_unregistered: int


def select_passage(
    model: SelectionModel,
    user_id: str,
    candidates: Iterable[PassageCandidate],
    *,
    seen_passage_ids: Collection[str] = (),
    seen_item_ids: Collection[str] = (),
    config: SelectionConfig = SelectionConfig(),
) -> SelectionResult:
    """후보를 평가하고 다음 지문을 반환한다. 모델과 노출 기록은 수정하지 않는다."""
    by_id: dict[str, PassageCandidate] = {}
    for passage in candidates:
        if by_id.setdefault(passage.passage_id, passage) != passage:
            raise ValueError(f"conflicting candidates for passage {passage.passage_id!r}")

    excluded_seen = excluded_unregistered = 0
    scored = []
    for passage in by_id.values():
        if passage.passage_id in seen_passage_ids or any(q.item_id in seen_item_ids for q in passage.questions):
            excluded_seen += 1
            continue
        try:
            probabilities = tuple(float(model.predict(user_id, q.item_id)) for q in passage.questions)
        except KeyError:
            excluded_unregistered += 1
            continue
        if any(not 0 <= p <= 1 for p in probabilities):
            raise ValueError(f"invalid predicted probability for passage {passage.passage_id!r}")
        n = len(probabilities)
        distance = fsum(abs(p - config.target_p) for p in probabilities) / n
        scores = PassageScores(probabilities, fsum(probabilities) / n, config.target_p, distance, 1.0 - distance)
        tie = sha256(f"{user_id}\0{passage.passage_id}".encode()).digest()
        scored.append(((-scores.total_score, distance, tie, passage.passage_id), passage, scores))

    if not scored:
        reason = "no_eligible_passage" if by_id else "empty_catalog"
        return SelectionResult(None, None, (reason,), 0, excluded_seen, excluded_unregistered)
    _, passage, scores = min(scored, key=lambda row: row[0])
    return SelectionResult(passage, scores, ("target_fit",), len(scored), excluded_seen, excluded_unregistered)
