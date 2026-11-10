"""Learning Analytics V1의 정규화된 JSON 이벤트."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from typing import ClassVar, Literal

from .skills import SKILLS

EVENT_VERSION = 1
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", re.ASCII)


class EventValidationError(ValueError):
    """잘못된 스키마나 인과관계를 가진 이벤트."""


def parse_timestamp(value: object, field: str = "occurred_at") -> datetime:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise EventValidationError(f"{field} must be an ISO timestamp with an explicit UTC offset")
    # datetime.fromisoformat은 +01:60 같은 비정규 오프셋도 정규화한다.
    if not value.endswith("Z") and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise EventValidationError(f"invalid {field} offset: {value!r}")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise EventValidationError(f"invalid {field}: {value!r}") from error


def require_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise EventValidationError(f"{field} must be a nonempty string without surrounding whitespace")
    return value


@dataclass(frozen=True)
class LearningEvent:
    kind: ClassVar[str]
    event_id: str
    user_id: str
    exposure_id: str
    occurred_at: datetime

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["occurred_at"] = self.occurred_at.isoformat().replace("+00:00", "Z")
        if isinstance(self, Exposure):
            payload["item_ids"] = list(self.item_ids)
        return {"version": EVENT_VERSION, "type": self.kind, **payload}


@dataclass(frozen=True)
class Exposure(LearningEvent):
    kind = "exposure"
    passage_id: str
    quiz_version: str
    item_ids: tuple[str, ...]
    policy_version: str | None = None


@dataclass(frozen=True)
class Submission(LearningEvent):
    kind = "submission"
    submission_id: str
    passage_id: str
    item_id: str
    item_version: str
    skill: str
    is_correct: bool
    is_retry: bool
    hint_used: bool | None = None


@dataclass(frozen=True)
class Completion(LearningEvent):
    kind = "completion"
    status: Literal["completed", "abandoned"]


Event = Exposure | Submission | Completion


def parse_event(payload: Mapping) -> Event:
    """V1 JSON 객체를 검증하고 시각과 선택 필드를 정규화한다."""
    if not isinstance(payload, Mapping) or any(not isinstance(key, str) for key in payload):
        raise EventValidationError("event must be an object with string keys")
    if type(payload.get("version")) is not int or payload["version"] != EVENT_VERSION:
        raise EventValidationError("unsupported event version; expected integer 1")
    kind = payload.get("type")
    if kind == "exposure":
        event_class, optional = Exposure, {"policy_version"}
    elif kind == "submission":
        event_class, optional = Submission, {"hint_used"}
    elif kind == "completion":
        event_class, optional = Completion, set()
    else:
        raise EventValidationError("unsupported event type")
    allowed = {"version", "type"} | {field.name for field in fields(event_class)}
    missing = allowed - optional - payload.keys()
    extra = payload.keys() - allowed
    if missing or extra:
        raise EventValidationError(f"event missing fields {sorted(missing)} or unexpected fields {sorted(extra)}")

    common = {key: require_id(payload[key], key) for key in ("event_id", "user_id", "exposure_id")}
    timestamp = parse_timestamp(payload["occurred_at"])
    if event_class is Exposure:
        raw_items = payload["item_ids"]
        if not isinstance(raw_items, list) or not raw_items:
            raise EventValidationError("item_ids must be a nonempty JSON array")
        item_ids = tuple(require_id(item_id, "item_ids entry") for item_id in raw_items)
        if len(set(item_ids)) != len(item_ids):
            raise EventValidationError("item_ids must be distinct")
        policy = payload.get("policy_version")
        return Exposure(
            **common, occurred_at=timestamp, passage_id=require_id(payload["passage_id"], "passage_id"),
            quiz_version=require_id(payload["quiz_version"], "quiz_version"), item_ids=item_ids,
            policy_version=None if policy is None else require_id(policy, "policy_version"),
        )
    if event_class is Submission:
        identifiers = {
            key: require_id(payload[key], key) for key in ("submission_id", "passage_id", "item_id", "item_version")
        }
        skill = payload["skill"]
        if skill not in SKILLS:
            raise EventValidationError("invalid skill")
        for field in ("is_correct", "is_retry"):
            if type(payload[field]) is not bool:
                raise EventValidationError(f"{field} must be a boolean")
        hint = payload.get("hint_used")
        if hint is not None and type(hint) is not bool:
            raise EventValidationError("hint_used must be a boolean or null")
        return Submission(
            **common, **identifiers, occurred_at=timestamp, skill=skill, is_correct=payload["is_correct"],
            is_retry=payload["is_retry"], hint_used=hint,
        )
    status = payload["status"]
    if status not in ("completed", "abandoned"):
        raise EventValidationError("status must be completed or abandoned")
    return Completion(**common, occurred_at=timestamp, status=status)


def parse_sequence(value: object, *, allow_zero: bool = False) -> int:
    if isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]{0,18}", value):
        value = int(value)
    if type(value) is not int or not (0 if allow_zero else 1) <= value <= 2**63 - 1:
        raise EventValidationError("invalid sequence; expected a canonical signed 64-bit position")
    return value


@dataclass(frozen=True)
class EventEnvelope:
    sequence: int
    applied_at: datetime
    event: Event

    def to_dict(self) -> dict:
        return {
            "sequence": str(self.sequence),
            "applied_at": self.applied_at.isoformat().replace("+00:00", "Z"),
            "event": self.event.to_dict(),
        }


def parse_envelope(payload: Mapping) -> EventEnvelope:
    if not isinstance(payload, Mapping) or payload.keys() != {"sequence", "applied_at", "event"}:
        raise EventValidationError("envelope requires sequence, applied_at and event")
    sequence = parse_sequence(payload["sequence"])
    applied_at = parse_timestamp(payload["applied_at"], "applied_at")
    event = parse_event(payload["event"])
    if applied_at < event.occurred_at:
        raise EventValidationError("applied_at cannot precede occurred_at")
    return EventEnvelope(sequence, applied_at, event)
