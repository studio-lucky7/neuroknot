"""단일 프로세스의 학습 이벤트 처리와 전역 Elo 재생."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime

from .elo import EloModel
from .learning_events import Completion, EventValidationError, Exposure, Submission, parse_event, require_id
from .skills import SKILLS

Event = Exposure | Submission | Completion


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

    def to_dict(self) -> dict:
        return {"event": self.event.to_dict(), "attempt": None if self.attempt is None else asdict(self.attempt)}


def _event_key(event: Event) -> tuple[str, str]:
    return (event.kind, event.submission_id if isinstance(event, Submission) else event.exposure_id)


class LearningHistory:
    """고정된 초기 카탈로그로 모든 사용자의 이벤트를 한 순서로 처리한다."""

    def __init__(
        self, items: Iterable[CatalogItem], *, onboarding_levels: Mapping[str, str | None] | None = None,
    ) -> None:
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

    @property
    def records(self) -> tuple[EventRecord, ...]:
        """집계에 사용할 효과가 있는 레코드. 재전송은 한 번만 포함한다."""
        return tuple(self._processed.values())

    def event_log(self) -> list[dict]:
        """재생에 사용할 입력 이력. 수락한 별칭 이벤트 ID도 보존한다."""
        events = sorted(self._receipts.values(), key=lambda event: event.occurred_at)
        return [event.to_dict() for event in events]

    def user_rating(self, user_id: str, skill: str) -> float:
        return float(self._model.user_rating(user_id, skill))

    def item_difficulty(self, item_id: str) -> float:
        return float(self._model.item_difficulty(item_id))

    def apply(self, payload: Mapping) -> EventRecord:
        """정규화한 신규 이벤트를 수락하거나, 재전송이면 기존 레코드를 반환한다."""
        return self._apply(parse_event(payload))

    def _apply(self, event: Event) -> EventRecord:
        key = _event_key(event)
        prior_receipt = self._receipts.get(event.event_id)
        if prior_receipt is not None:
            if prior_receipt != event:
                raise EventConflictError(f"conflicting event_id: {event.event_id!r}")
            return self._processed[key]
        prior_record = self._processed.get(key)
        if prior_record is not None:
            if replace(prior_record.event, event_id=event.event_id) != event:
                raise EventConflictError(f"conflicting {key[0]} ID: {key[1]!r}")
            self._receipts[event.event_id] = event
            return prior_record
        if self._last_at is not None and event.occurred_at < self._last_at:
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
                attempt = self._submit(event, exposure)
            elif event.status == "completed" and not self._answered[event.exposure_id].issuperset(exposure.item_ids):
                raise EventValidationError("completion requires an answer for every exposed item")

        record = EventRecord(event, attempt)
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
        if ("completion", event.exposure_id) in self._processed:
            raise EventValidationError("exposure has already ended")
        return exposure

    def _submit(self, event: Submission, exposure: Exposure) -> AttemptTrace:
        if exposure.passage_id != event.passage_id or event.item_id not in exposure.item_ids:
            raise EventValidationError("submission passage or item does not match exposure")
        item = self._items[event.item_id]
        if (event.item_version, event.skill) != (item.item_version, item.skill):
            raise EventValidationError("submission item version or skill does not match catalog")
        key = (event.user_id, event.item_id)
        if event.is_retry != (key in self._first_answers):
            raise EventValidationError("is_retry must match whether a valid first answer already exists")

        theta_before = self.user_rating(event.user_id, event.skill)
        difficulty_before = self.item_difficulty(event.item_id)
        if event.is_retry:
            probability = self._model.predict(event.user_id, event.item_id)
        else:
            probability = self._model.update(event.user_id, event.item_id, event.is_correct)
            self._first_answers.add(key)
        self._answered[event.exposure_id].add(event.item_id)
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
