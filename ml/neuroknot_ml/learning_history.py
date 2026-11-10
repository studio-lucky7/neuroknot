"""단일 프로세스의 학습 이벤트 처리와 전역 Elo 재생."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from threading import RLock

from .elo import EloModel
from .learning_events import (
    Completion, Event, EventEnvelope, EventValidationError, Exposure, Submission,
    parse_envelope, parse_event, require_id,
)
from .selection import PassageCandidate, SelectionConfig, SelectionResult, register_passage, select_passage
from .skills import SKILLS


class EventConflictError(EventValidationError):
    """이미 사용한 이벤트 또는 업무 ID에 다른 데이터가 전달됨."""


@dataclass(frozen=True)
class CatalogItem:
    """문항 버전마다 고유 ID 하나를 Elo에 등록한다."""

    item_id: str
    item_version: str
    skill: str
    difficulty: int | None = None

    def __post_init__(self) -> None:
        require_id(self.item_id, "item_id")
        require_id(self.item_version, "item_version")
        if self.skill not in SKILLS:
            raise EventValidationError(f"invalid skill for item {self.item_id!r}")
        stars = self.difficulty
        if stars is not None and (type(stars) is not int or not 1 <= stars <= 5):
            raise EventValidationError("difficulty must be an integer from 1 to 5 or null")


@dataclass(frozen=True)
class QuizManifest:
    passage_id: str
    quiz_version: str
    item_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        require_id(self.passage_id, "passage_id")
        require_id(self.quiz_version, "quiz_version")
        if not isinstance(self.item_ids, tuple) or len(self.item_ids) != 3:
            raise EventValidationError("quiz manifest requires three item IDs")
        for item_id in self.item_ids:
            require_id(item_id, "item_id")
        if len(set(self.item_ids)) != 3:
            raise EventValidationError("quiz manifest item IDs must be distinct")


@dataclass(frozen=True)
class Recommendation:
    through_sequence: int | None
    selection: SelectionResult


@dataclass(frozen=True)
class _SelectionView:
    probabilities: Mapping[str, float]
    ratings: Mapping[str, float]

    def predict(self, user_id: str, item_id: str) -> float:
        return self.probabilities[item_id]

    def user_rating(self, user_id: str, skill: str) -> float:
        return self.ratings[skill]


@dataclass(frozen=True)
class AttemptTrace:
    probability: float
    theta_before: float
    theta_after: float
    difficulty_before: float
    difficulty_after: float
    elo_updated: bool


@dataclass(frozen=True)
class EventRecord:
    event: Event
    attempt: AttemptTrace | None = None
    sequence: int | None = None
    applied_at: datetime | None = None

    def to_dict(self) -> dict:
        payload = {"event": self.event.to_dict(), "attempt": None if self.attempt is None else asdict(self.attempt)}
        if self.applied_at is not None:
            payload["sequence"] = str(self.sequence)
            payload["applied_at"] = self.applied_at.isoformat().replace("+00:00", "Z")
        return payload


def _event_key(event: Event) -> tuple[str, str]:
    return (event.kind, event.submission_id if isinstance(event, Submission) else event.exposure_id)


class LearningHistory:
    """모든 사용자의 이벤트와 공유 Elo를 소유한다."""

    def __init__(
        self, items: Iterable[CatalogItem], *, onboarding_levels: Mapping[str, str | None] | None = None,
        quiz_catalog: Iterable[QuizManifest] = (),
    ) -> None:
        self._lock = RLock()
        self._model = EloModel()
        self._items: dict[str, CatalogItem] = {}
        for item in items:
            if item.item_id in self._items:
                raise EventValidationError(f"duplicate catalog item ID: {item.item_id!r}")
            self._items[item.item_id] = item
            self._model.register_item(item.item_id, item.skill, item.difficulty)
        self._quizzes: dict[tuple[str, str], QuizManifest] = {}
        for quiz in quiz_catalog:
            key = (quiz.passage_id, quiz.quiz_version)
            if key in self._quizzes or any(item_id not in self._items for item_id in quiz.item_ids):
                raise EventValidationError("duplicate quiz version or unknown quiz item")
            if len({self._items[item_id].skill for item_id in quiz.item_ids}) != 3:
                raise EventValidationError("quiz manifest requires three distinct skills")
            self._quizzes[key] = quiz
        for user_id, level in (onboarding_levels or {}).items():
            require_id(user_id, "onboarding user_id")
            if level is not None:
                require_id(level, "onboarding level")
            self._model.register_user(user_id, level)

        self._receipts: dict[str, Event] = {}
        self._processed: dict[tuple[str, str], EventRecord] = {}
        self._answered: dict[str, set[str]] = {}
        self._first_answers: set[tuple[str, str]] = set()
        self._last_at: datetime | None = None
        self._journal: list[tuple[EventEnvelope, EventRecord]] = []

    @property
    def records(self) -> tuple[EventRecord, ...]:
        """집계에 사용할 효과가 있는 레코드. 재전송은 한 번만 포함한다."""
        return self.read_records()[1]

    def read_records(self) -> tuple[int | None, tuple[EventRecord, ...]]:
        """같은 커서에서 확정된 커서와 불변 레코드를 읽는다."""
        with self._lock:
            cursor = None if self._receipts and not self._journal else len(self._journal)
            return cursor, tuple(self._processed.values())

    def event_log(self) -> list[dict]:
        """재생에 사용할 입력 이력. 순번 스트림은 봉투를 반환한다."""
        with self._lock:
            if self._journal:
                return [envelope.to_dict() for envelope, _ in self._journal]
            events = sorted(self._receipts.values(), key=lambda event: event.occurred_at)
            return [event.to_dict() for event in events]

    def user_rating(self, user_id: str, skill: str) -> float:
        with self._lock:
            return float(self._model.user_rating(user_id, skill))

    def item_difficulty(self, item_id: str) -> float:
        with self._lock:
            return float(self._model.item_difficulty(item_id))

    def predict(self, user_id: str, item_id: str) -> float:
        with self._lock:
            return self._model.predict(user_id, item_id)

    @property
    def catalog(self) -> tuple[CatalogItem, ...]:
        with self._lock:
            return tuple(self._items.values())

    @property
    def quiz_catalog(self) -> tuple[QuizManifest, ...]:
        with self._lock:
            return tuple(self._quizzes.values())

    def register_generated(
        self,
        generated: Mapping,
        item_ids: Sequence[str],
        *,
        quiz_version: str,
        item_versions: Mapping[str, str],
        item_difficulties: Mapping[str, int | None] | None = None,
    ) -> PassageCandidate:
        """Generation 문항을 공용 카탈로그와 Elo에 원자적으로 등록한다."""
        candidate = PassageCandidate.from_generated(generated, item_ids)
        quiz = QuizManifest(candidate.passage_id, quiz_version, tuple(q.item_id for q in candidate.questions))
        if item_versions.keys() != set(quiz.item_ids):
            raise EventValidationError("item_versions must match the candidate's item IDs")
        overrides = {} if item_difficulties is None else dict(item_difficulties)
        additions = {}
        with self._lock:
            key = (quiz.passage_id, quiz.quiz_version)
            if self._quizzes.get(key, quiz) != quiz:
                raise EventValidationError("quiz version is already bound to different item IDs")
            for question in candidate.questions:
                item_id = question.item_id
                stars = overrides.get(item_id)
                item = CatalogItem(
                    item_id, item_versions[item_id], question.skill,
                    candidate.difficulty_hint if stars is None else stars,
                )
                existing = self._items.get(item_id)
                if existing is None:
                    additions[item_id] = item
                elif (existing.item_version, existing.skill) != (item.item_version, item.skill):
                    raise EventValidationError("item ID is already bound to another version or skill")
            if key not in self._quizzes:
                quizzes = {**self._quizzes, key: quiz}
                for record in self._processed.values():
                    if isinstance(record.event, Exposure):
                        _validate_quiz_exposure(record.event, quizzes)
            register_passage(self._model, candidate, item_difficulties=overrides)
            self._items.update(additions)
            self._quizzes[key] = quiz
        return candidate

    def recommend(
        self, user_id: str, candidates: Iterable[PassageCandidate], *, config: SelectionConfig = SelectionConfig(),
    ) -> Recommendation:
        """모델 점수와 이력을 한 커서에서 복사한 뒤 Core 선택기를 실행한다."""
        require_id(user_id, "user_id")
        candidates = tuple(candidates)
        with self._lock:
            cursor, records = self.read_records()
            quiz_items = {(quiz.passage_id, quiz.item_ids) for quiz in self._quizzes.values()}
            probabilities = {}
            for candidate in candidates:
                key = (candidate.passage_id, tuple(q.item_id for q in candidate.questions))
                if key not in quiz_items:
                    raise EventValidationError("candidate is not registered in the quiz catalog")
                for question in candidate.questions:
                    if self._items[question.item_id].skill != question.skill:
                        raise EventValidationError("candidate skill does not match catalog")
                    if question.item_id not in probabilities:
                        probabilities[question.item_id] = self._model.predict(user_id, question.item_id)
            view = _SelectionView(probabilities, {skill: self._model.user_rating(user_id, skill) for skill in SKILLS})
            seen_passages, seen_items = set(), set()
            counts = dict.fromkeys(SKILLS, 0)
            for record in records:
                event = record.event
                if event.user_id != user_id:
                    continue
                if isinstance(event, Exposure):
                    seen_passages.add(event.passage_id)
                    seen_items.update(event.item_ids)
                elif isinstance(event, Submission) and not event.is_retry:
                    counts[event.skill] += 1
        return Recommendation(cursor, select_passage(
            view, user_id, candidates, seen_passage_ids=seen_passages, seen_item_ids=seen_items,
            skill_attempts=counts, config=config,
        ))

    def apply(self, payload: Mapping) -> EventRecord:
        """순번 도입 이전의 이벤트를 처리한다."""
        event = parse_event(payload)
        with self._lock:
            if self._journal:
                raise EventValidationError("legacy and sequenced events cannot be mixed")
            return self._apply(event)

    def accept_event(self, payload: Mapping, *, applied_at: str) -> EventRecord:
        """서버 경계에서 다음 순번을 발급한다. 동일 ID 재전송에는 새 순번을 부여하지 않는다."""
        event = parse_event(payload)
        with self._lock:
            self._require_sequenced()
            previous = self._receipt(event)
            if previous is not None:
                return previous
            envelope = parse_envelope({
                "sequence": len(self._journal) + 1, "applied_at": applied_at, "event": event.to_dict(),
            })
            return self._apply_envelope(envelope)

    def apply_envelope(self, payload: Mapping) -> EventRecord:
        """이미 발급한 순번의 봉투를 순서대로 적용한다."""
        envelope = parse_envelope(payload)
        with self._lock:
            return self._apply_envelope(envelope)

    def _require_sequenced(self) -> None:
        if self._receipts and not self._journal:
            raise EventValidationError("legacy and sequenced events cannot be mixed")

    def _apply_envelope(self, envelope: EventEnvelope, *, restored_attempt: AttemptTrace | None = None) -> EventRecord:
        self._require_sequenced()
        sequence = envelope.sequence
        if sequence <= len(self._journal):
            previous, record = self._journal[sequence - 1]
            if previous != envelope:
                raise EventConflictError(f"conflicting sequence: {sequence}")
            return record
        if sequence != len(self._journal) + 1:
            raise EventValidationError("missing sequence before envelope")
        if envelope.event.event_id in self._receipts:
            raise EventConflictError("event_id is already bound to an earlier sequence")
        if self._journal and envelope.applied_at < self._journal[-1][0].applied_at:
            raise EventValidationError("applied_at must be nondecreasing")
        record = self._apply(envelope.event, envelope=envelope, restored_attempt=restored_attempt)
        self._journal.append((envelope, record))
        return record

    def _receipt(self, event: Event) -> EventRecord | None:
        prior_receipt = self._receipts.get(event.event_id)
        if prior_receipt is not None:
            if prior_receipt != event:
                raise EventConflictError(f"conflicting event_id: {event.event_id!r}")
            return self._processed[_event_key(event)]
        return None

    def _apply(
        self, event: Event, *, envelope: EventEnvelope | None = None, restored_attempt: AttemptTrace | None = None,
    ) -> EventRecord:
        previous = self._receipt(event)
        if previous is not None:
            return previous
        key = _event_key(event)
        prior_record = self._processed.get(key)
        if prior_record is not None:
            if replace(prior_record.event, event_id=event.event_id) != event:
                raise EventConflictError(f"conflicting {key[0]} ID: {key[1]!r}")
            self._receipts[event.event_id] = event
            return prior_record
        if envelope is None and self._last_at is not None and event.occurred_at < self._last_at:
            raise EventValidationError("new events must be processed in chronological order")

        attempt = None
        if isinstance(event, Exposure):
            for item_id in event.item_ids:
                if item_id not in self._items:
                    raise EventValidationError(f"unknown exposed item: {item_id!r}")
            _validate_quiz_exposure(event, self._quizzes)
            self._answered[event.exposure_id] = set()
        else:
            exposure = self._active_exposure(event)
            if isinstance(event, Submission):
                attempt = self._submit(event, exposure, restored_attempt)
            elif event.status == "completed" and not self._answered[event.exposure_id].issuperset(exposure.item_ids):
                raise EventValidationError("completion requires an answer for every exposed item")

        record = EventRecord(
            event, attempt, None if envelope is None else envelope.sequence,
            None if envelope is None else envelope.applied_at,
        )
        self._receipts[event.event_id] = event
        self._processed[key] = record
        self._last_at = event.occurred_at
        return record

    def _active_exposure(self, event: Submission | Completion) -> Exposure:
        record = self._processed.get(("exposure", event.exposure_id))
        if record is None:
            raise EventValidationError(f"unknown exposure: {event.exposure_id!r}")
        exposure = record.event
        assert isinstance(exposure, Exposure)
        if exposure.user_id != event.user_id:
            raise EventValidationError("event user does not match exposure user")
        if event.occurred_at < exposure.occurred_at:
            raise EventValidationError("event occurred before exposure")
        if ("completion", event.exposure_id) in self._processed:
            raise EventValidationError("exposure has already ended")
        return exposure

    def _submit(self, event: Submission, exposure: Exposure, restored_attempt: AttemptTrace | None) -> AttemptTrace:
        if exposure.passage_id != event.passage_id or event.item_id not in exposure.item_ids:
            raise EventValidationError("submission passage or item does not match exposure")
        item = self._items[event.item_id]
        if (event.item_version, event.skill) != (item.item_version, item.skill):
            raise EventValidationError("submission item version or skill does not match catalog")
        key = (event.user_id, event.item_id)
        if event.is_retry != (key in self._first_answers):
            raise EventValidationError("is_retry must match whether a valid first answer already exists")

        trace = self._trace_answer(event) if restored_attempt is None else restored_attempt
        if trace.elo_updated == event.is_retry:
            raise EventValidationError("attempt trace does not match retry status")
        if not event.is_retry:
            self._first_answers.add(key)
        self._answered[event.exposure_id].add(event.item_id)
        return trace

    def _trace_answer(self, event: Submission) -> AttemptTrace:
        theta_before = self.user_rating(event.user_id, event.skill)
        difficulty_before = self.item_difficulty(event.item_id)
        if event.is_retry:
            probability = self._model.predict(event.user_id, event.item_id)
        else:
            probability = self._model.update(event.user_id, event.item_id, event.is_correct)
        return AttemptTrace(
            probability=probability,
            theta_before=theta_before,
            theta_after=self.user_rating(event.user_id, event.skill),
            difficulty_before=difficulty_before,
            difficulty_after=self.item_difficulty(event.item_id),
            elo_updated=not event.is_retry,
        )

    @classmethod
    def replay(
        cls,
        items: Iterable[CatalogItem],
        events: Iterable[Mapping],
        *,
        onboarding_levels: Mapping[str, str | None] | None = None,
    ) -> LearningHistory:
        """전 사용자의 이벤트를 시간순으로 재생한다. 동시각에는 입력 순서를 유지한다."""
        parsed = sorted((parse_event(payload) for payload in events), key=lambda event: event.occurred_at)
        history = cls(items, onboarding_levels=onboarding_levels)
        for event in parsed:
            history._apply(event)
        return history

    @classmethod
    def replay_envelopes(
        cls,
        items: Iterable[CatalogItem],
        envelopes: Iterable[Mapping],
        *,
        onboarding_levels: Mapping[str, str | None] | None = None,
        quiz_catalog: Iterable[QuizManifest] = (),
    ) -> LearningHistory:
        """발급된 전역 순번으로 재생한다."""
        history = cls(items, onboarding_levels=onboarding_levels, quiz_catalog=quiz_catalog)
        history.replay_suffix(envelopes)
        return history

    def replay_suffix(self, envelopes: Iterable[Mapping]) -> None:
        parsed = sorted((parse_envelope(payload) for payload in envelopes), key=lambda envelope: envelope.sequence)
        with self._lock:
            for envelope in parsed:
                self._apply_envelope(envelope)


def _validate_quiz_exposure(event: Exposure, quizzes: Mapping[tuple[str, str], QuizManifest]) -> None:
    quiz = quizzes.get((event.passage_id, event.quiz_version))
    if quiz is not None:
        if quiz.item_ids != event.item_ids:
            raise EventValidationError("exposure items do not match quiz version")
    elif any(
        known.passage_id == event.passage_id or any(item_id in known.item_ids for item_id in event.item_ids)
        for known in quizzes.values()
    ):
        raise EventValidationError("exposure does not match a registered passage and quiz version")
