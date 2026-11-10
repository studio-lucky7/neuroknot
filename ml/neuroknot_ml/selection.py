"""Elo와 분리된 지문 단위 콘텐츠 선택 정책."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from math import fsum, isfinite
from typing import Protocol

from .elo import EloModel
from .skills import SKILLS


def _validate_stars(value: int | None, field: str) -> None:
    if value is not None and (type(value) is not int or not 1 <= value <= 5):
        raise ValueError(f"{field} must be an integer from 1 to 5 or None")


class SelectionModel(Protocol):
    def predict(self, user_id: str, item_id: str) -> float: ...

    def user_rating(self, user_id: str, skill: str) -> float: ...


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
        _validate_stars(self.difficulty_hint, "difficulty_hint")
        object.__setattr__(self, "questions", questions)

    @classmethod
    def from_generated(cls, generated: Mapping, item_ids: Sequence[str]) -> PassageCandidate:
        """GeneratedQuiz JSON과 호출자가 부여한 문항 ID를 문항 순서대로 연결한다."""
        try:
            passage_id = generated["passage_id"]
            quiz = generated["quiz"]
            if not isinstance(quiz, Mapping):
                raise TypeError("quiz must be a mapping")
            skills = tuple(question["skill"] for question in quiz["questions"])
            hint = quiz.get("difficulty_hint")
        except (KeyError, TypeError) as error:
            raise ValueError("invalid GeneratedQuiz passage_id, quiz or questions") from error
        if (
            not isinstance(item_ids, Sequence) or isinstance(item_ids, (str, bytes))
            or len(item_ids) != 3 or len(skills) != 3
        ):
            raise ValueError("GeneratedQuiz requires exactly three questions and three item IDs")
        return cls(passage_id, tuple(PassageQuestion(i, s) for i, s in zip(item_ids, skills)), hint)


def register_passage(
    model: EloModel,
    passage: PassageCandidate,
    *,
    item_difficulties: Mapping[str, int | None] | None = None,
) -> None:
    """신규 문항을 문항별 별점 또는 지문 힌트로 초기화한다."""
    overrides = {} if item_difficulties is None else item_difficulties
    item_ids = {question.item_id for question in passage.questions}
    for item_id, stars in overrides.items():
        if item_id not in item_ids:
            raise ValueError(f"difficulty provided for unknown item ID: {item_id!r}")
        _validate_stars(stars, f"item_difficulties[{item_id!r}]")

    new_questions = []
    for question in passage.questions:
        try:
            skill = model.item_skill(question.item_id)
        except KeyError:
            new_questions.append(question)
        else:
            if skill != question.skill:
                raise ValueError(f"item {question.item_id!r} is already registered for skill {skill!r}")

    for question in new_questions:
        stars = overrides.get(question.item_id)
        model.register_item(question.item_id, question.skill, passage.difficulty_hint if stars is None else stars)


@dataclass(frozen=True)
class SelectionConfig:
    target_p: float = 0.7
    cold_start_target_p: float = 0.8
    cold_start_attempts: int = 6
    weakness_min_attempts: int = 2
    weakness_weight: float = 0.2
    coverage_weight: float = 0.15

    def __post_init__(self) -> None:
        for field in ("target_p", "cold_start_target_p"):
            if not 0 < getattr(self, field) < 1:
                raise ValueError(f"{field} must be between 0 and 1")
        for field, minimum in (("cold_start_attempts", 0), ("weakness_min_attempts", 1)):
            value = getattr(self, field)
            if type(value) is not int or value < minimum:
                raise ValueError(f"{field} must be an integer >= {minimum}")
        for field in ("weakness_weight", "coverage_weight"):
            if not 0 <= getattr(self, field) <= 1:
                raise ValueError(f"{field} must be in [0, 1]")


@dataclass(frozen=True)
class PassageScores:
    probabilities: tuple[float, ...]
    mean_probability: float
    target_p: float
    target_distance: float
    weakness_bonus: float
    coverage_bonus: float
    total_score: float


@dataclass(frozen=True)
class SelectionResult:
    passage: PassageCandidate | None
    scores: PassageScores | None
    reasons: tuple[str, ...]
    eligible_count: int
    excluded_seen: int
    excluded_unregistered: int


def _weakest_skills(model: SelectionModel, user_id: str, counts: Mapping[str, int], minimum: int) -> set[str]:
    supported = [skill for skill in SKILLS if counts[skill] >= minimum]
    if len(supported) < 2:
        return set()
    ratings = {skill: model.user_rating(user_id, skill) for skill in supported}
    if not all(isfinite(rating) for rating in ratings.values()):
        raise ValueError("user ratings must be finite")
    lowest, highest = min(ratings.values()), max(ratings.values())
    if lowest == highest:
        return set()
    return {skill for skill, rating in ratings.items() if rating == lowest}


def select_passage(
    model: SelectionModel,
    user_id: str,
    candidates: Iterable[PassageCandidate],
    *,
    seen_passage_ids: Collection[str] = (),
    seen_item_ids: Collection[str] = (),
    skill_attempts: Mapping[str, int] | None = None,
    config: SelectionConfig = SelectionConfig(),
) -> SelectionResult:
    """누적 첫 응답 수와 노출 기록을 바탕으로 다음 지문을 고른다. 입력은 수정하지 않는다."""
    counts = dict.fromkeys(SKILLS, 0)
    for skill, attempts in (skill_attempts or {}).items():
        if skill not in counts or type(attempts) is not int or attempts < 0:
            raise ValueError(f"invalid skill attempt count for {skill!r}")
        counts[skill] = attempts
    cold_start = sum(counts.values()) < config.cold_start_attempts
    target = max(config.target_p, config.cold_start_target_p) if cold_start else config.target_p
    max_count = max(counts.values())

    by_id: dict[str, PassageCandidate] = {}
    for passage in candidates:
        if by_id.setdefault(passage.passage_id, passage) != passage:
            raise ValueError(f"conflicting candidates for passage {passage.passage_id!r}")

    excluded_seen = excluded_unregistered = 0
    scored = []
    weakest = None
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
        if weakest is None:
            weakest = set() if cold_start else _weakest_skills(model, user_id, counts, config.weakness_min_attempts)
        n = len(probabilities)
        distance = fsum(abs(p - target) for p in probabilities) / n
        weakness = config.weakness_weight * sum(q.skill in weakest for q in passage.questions) / n
        coverage = 0.0
        if max_count:
            deficit = fsum((max_count - counts[q.skill]) / max_count for q in passage.questions)
            coverage = config.coverage_weight * deficit / n
        scores = PassageScores(
            probabilities, fsum(probabilities) / n, target, distance, weakness, coverage,
            1.0 - distance + weakness + coverage,
        )
        tie = sha256(f"{user_id}\0{passage.passage_id}".encode()).digest()
        scored.append(((-scores.total_score, distance, tie, passage.passage_id), passage, scores))

    if not scored:
        reason = "no_eligible_passage" if by_id else "empty_catalog"
        return SelectionResult(None, None, (reason,), 0, excluded_seen, excluded_unregistered)
    _, passage, scores = min(scored, key=lambda row: row[0])
    reasons = ["cold_start" if cold_start else "target_fit"]
    if scores.weakness_bonus > 0:
        reasons.append("weak_skill")
    if scores.coverage_bonus > 0:
        reasons.append("skill_coverage")
    return SelectionResult(passage, scores, tuple(reasons), len(scored), excluded_seen, excluded_unregistered)
