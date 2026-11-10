"""단일 프로세스의 학습 이벤트 처리와 전역 Elo 재생."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from threading import RLock

from .elo import EloModel
from .learning_events import (
    Completion, Event, EventEnvelope, EventValidationError, Exposure, Submission,
    parse_envelope, parse_event, require_id,
)
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
    """고정된 초기 카탈로그로 모든 사용자의 이벤트를 한 순서로 처리한다."""

    def __init__(
        self, items: Iterable[CatalogItem], *, onboarding_levels: Mapping[str, str | None] | None = None,
    ) -> None:
        self._lock = RLock()
        self._model = EloModel()
        self._items: dict[str, CatalogItem] = {}
        for item in items:
            if item.item_id in self._items:
                raise EventValidationError(f"duplicate catalog item ID: {item.item_id!r}")
            self._items[item.item_id] = item
            self._model.register_item(item.item_id, item.skill, item.difficulty)
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
    ) -> LearningHistory:
        """발급된 전역 순번으로 재생한다."""
        history = cls(items, onboarding_levels=onboarding_levels)
        history.replay_suffix(envelopes)
        return history

    def replay_suffix(self, envelopes: Iterable[Mapping]) -> None:
        parsed = sorted((parse_envelope(payload) for payload in envelopes), key=lambda envelope: envelope.sequence)
        with self._lock:
            for envelope in parsed:
                self._apply_envelope(envelope)
